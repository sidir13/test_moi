import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  Sparkles, ChevronRight, CheckCircle2, BookOpen, Tag, Loader2,
  AlertCircle, BarChart2, Mic2
} from "lucide-react";

import {
  advanceStep,
  generateScenarios,
  fetchScenarios,
  selectScenario,
  fetchSelectedScenario,
  fetchScenarioProgress,
  fetchModels,
  type ScenarioProgressStep,
  synthesizeScenarioAudio
} from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type SentenceSourcing = { sentence: string; sources: string[] };

function getScenarioRank(raw?: Record<string, unknown>): number | null {
  if (!raw) return null;
  const immediate = parseRank((raw as Record<string, unknown>).quality_rank ?? (raw as Record<string, unknown>).rank);
  if (immediate !== null) return immediate;
  const payload = (raw as Record<string, unknown>).scenario ?? raw;
  return parseRank((payload as Record<string, unknown>)?.quality_rank ?? (payload as Record<string, unknown>)?.rank);
}

function parseRank(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) return parsed;
  }
  return null;
}

function isSameScenario(a?: Record<string, unknown>, b?: Record<string, unknown>) {
  if (!a || !b) return false;
  if ((a as Record<string, unknown>).scenario_index && (b as Record<string, unknown>).scenario_index)
    return (a as Record<string, unknown>).scenario_index === (b as Record<string, unknown>).scenario_index;
  const payloadA = (a as Record<string, unknown>).scenario ?? a;
  const payloadB = (b as Record<string, unknown>).scenario ?? b;
  if ((payloadA as Record<string, unknown>)?.id && (payloadB as Record<string, unknown>)?.id)
    return (payloadA as Record<string, unknown>).id === (payloadB as Record<string, unknown>).id;
  if ((payloadA as Record<string, unknown>)?.titre && (payloadB as Record<string, unknown>)?.titre)
    return (payloadA as Record<string, unknown>).titre === (payloadB as Record<string, unknown>).titre;
  return JSON.stringify(payloadA) === JSON.stringify(payloadB);
}

function extractErrorMessage(err: unknown): string | null {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail.trim().length > 0) return detail;
    if (typeof err.message === "string") return err.message;
  } else if (err instanceof Error) {
    return err.message;
  }
  return null;
}

const STATUS_LABELS: Record<string, string> = {
  running: "En cours",
  done: "Terminé",
  error: "Erreur",
  pending: "En attente"
};

const ANGLE_LABELS: Record<string, string> = {
  temoignage_croise: "Témoignages croisés",
  chronique_sociale: "Chronique sociale",
  journee_type: "Journée type",
  portrait_individuel: "Portrait individuel",
  avant_apres_evenement: "Avant / Après",
  mosaique_voix: "Mosaïque de voix",
  lettre_intime: "Lettre intime",
  recit_initiatique: "Récit initiatique"
};

export function ScenarioReviewView() {
  const { sessionId, setCurrentStep, scenarioTarget, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [prompt, setPrompt] = useState("");
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isAdvancing, setIsAdvancing] = useState(false);
  const [advanceError, setAdvanceError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const bootstrap = useRef(false);

  const modelsQuery = useQuery({ queryKey: ["models"], queryFn: fetchModels, staleTime: 600_000 });
  const scenariosQuery = useQuery({
    queryKey: ["scenarios", sessionId],
    queryFn: () => fetchScenarios(sessionId!),
    enabled: Boolean(sessionId)
  });
  const selectedScenarioQuery = useQuery({
    queryKey: ["selected-scenario", sessionId],
    queryFn: () => fetchSelectedScenario(sessionId!),
    enabled: Boolean(sessionId)
  });
  const progressQuery = useQuery({
    queryKey: ["scenario-progress", sessionId],
    queryFn: () => fetchScenarioProgress(sessionId!),
    enabled: Boolean(sessionId),
    refetchInterval: isGenerating ? 1500 : false
  });

  const sortedScenarios = useMemo(() => {
    if (!scenariosQuery.data) return [];
    return [...scenariosQuery.data].sort((a, b) => {
      const rankA = getScenarioRank(a);
      const rankB = getScenarioRank(b);
      if (rankA !== null && rankB !== null && rankA !== rankB) return rankA - rankB;
      if (rankA !== null) return -1;
      if (rankB !== null) return 1;
      const idxA = (a as Record<string, unknown>).scenario_index ?? Number.MAX_SAFE_INTEGER;
      const idxB = (b as Record<string, unknown>).scenario_index ?? Number.MAX_SAFE_INTEGER;
      return (idxA as number) - (idxB as number);
    });
  }, [scenariosQuery.data]);

  useEffect(() => {
    if (!sessionId || bootstrap.current) return;
    if (scenariosQuery.isLoading || scenariosQuery.isFetching) return;
    if (scenariosQuery.data && scenariosQuery.data.length > 0) return;
    bootstrap.current = true;
    triggerGeneration();
  }, [sessionId, scenariosQuery.data, scenariosQuery.isLoading, scenariosQuery.isFetching]);

  useEffect(() => {
    if (scenariosQuery.data && scenariosQuery.data.length > 0) updateProgress({ scenariosReady: true });
  }, [scenariosQuery.data, updateProgress]);

  useEffect(() => {
    if (selectedScenarioQuery.data) updateProgress({ scenarioChosen: true });
  }, [selectedScenarioQuery.data, updateProgress]);

  if (!sessionId) return <p className="text-sm text-muted-foreground">Session introuvable.</p>;

  const triggerGeneration = () => {
    if (!sessionId) return;
    setIsGenerating(true);
    progressQuery.refetch();
    const modelLabel = modelsQuery.data?.find((m) => m.id === selectedModel)?.label ?? "défaut";
    setStatus(`Génération avec ${modelLabel}…`);
    generateScenarios(sessionId, prompt, scenarioTarget, "simple", selectedModel || undefined)
      .then(() => {
        setStatus(`${scenarioTarget} scénarios générés.`);
        queryClient.invalidateQueries({ queryKey: ["scenarios", sessionId] });
      })
      .catch(() => setStatus("Génération impossible."))
      .finally(() => {
        setIsGenerating(false);
        progressQuery.refetch();
      });
  };

  const handleGenerate = (evt: FormEvent) => {
    evt.preventDefault();
    triggerGeneration();
  };

  const goNext = async () => {
    if (!sessionId) return;
    setAdvanceError(null);
    setIsAdvancing(true);
    try {
      const job = await synthesizeScenarioAudio(sessionId);
      if (job?.status && job.status !== "done") setStatus("Audio en cours de génération…");
    } catch (err) {
      setAdvanceError(extractErrorMessage(err) ?? "Erreur de génération audio. Vérifiez vos instructions vocales.");
      setIsAdvancing(false);
      return;
    }
    await advanceStep(sessionId, "scenario_review", { prompt });
    setCurrentStep("scenario_edit");
    navigate("/step/scenario_edit");
    setIsAdvancing(false);
  };

  const progressSteps = progressQuery.data ?? [];
  const completedSteps = progressSteps.filter((s) => s.status === "done").length;

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">Scénarios générés</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Consultez, comparez et sélectionnez le scénario qui vous convient.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            Régénérer les scénarios
          </CardTitle>
          <CardDescription>Affinez avec un prompt et choisissez un modèle LLM.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleGenerate} className="flex flex-col gap-3">
            <Textarea
              rows={4}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Souhaitez-vous orienter les scénarios ? (optionnel)"
            />
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1.5 flex-1 min-w-[200px]">
                <Label>Modèle LLM</Label>
                <Select value={selectedModel} onValueChange={setSelectedModel}>
                  <SelectTrigger>
                    <SelectValue placeholder="Par défaut (Opus 4.6)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Par défaut (Opus 4.6)</SelectItem>
                    {modelsQuery.data?.map((m) => (
                      <SelectItem key={m.id} value={m.id}>
                        {m.label} — {m.provider}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" disabled={isGenerating}>
                {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                {isGenerating ? "Génération…" : "Régénérer"}
              </Button>
            </div>
          </form>
          {status && <p className="text-sm text-muted-foreground mt-2">{status}</p>}
        </CardContent>
      </Card>

      {/* Scenarios list */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold">Scénarios disponibles</h3>
          {scenariosQuery.isLoading && (
            <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Chargement…
            </span>
          )}
        </div>
        {!scenariosQuery.isLoading && sortedScenarios.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucun scénario pour le moment.</p>
        )}
        {sortedScenarios.map((scenario, idx) => {
          const displayIndex = getScenarioRank(scenario) ?? idx + 1;
          const cardKey =
            (scenario as Record<string, unknown>).scenario_index ??
            `${idx}-${displayIndex}`;
          return (
            <ScenarioCard
              key={String(cardKey)}
              scenario={scenario}
              displayIndex={displayIndex}
              isSelected={isSameScenario(selectedScenarioQuery.data, scenario)}
              onSelect={async () => {
                await selectScenario(sessionId, scenario);
                queryClient.invalidateQueries({ queryKey: ["selected-scenario", sessionId] });
                updateProgress({ scenarioChosen: true });
              }}
            />
          );
        })}
      </div>

      {advanceError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{advanceError}</AlertDescription>
        </Alert>
      )}

      <Separator />
      <div className="flex items-center gap-3">
        <Button onClick={goNext} disabled={!selectedScenarioQuery.data || isAdvancing}>
          {isAdvancing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Continuer vers l'édition
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
        {!selectedScenarioQuery.data && (
          <p className="text-sm text-muted-foreground">Sélectionnez un scénario pour continuer.</p>
        )}
      </div>

      {/* Generation progress modal */}
      <Dialog open={isGenerating}>
        <DialogContent className="max-w-md" onInteractOutside={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              Génération en cours
            </DialogTitle>
            <DialogDescription>
              {completedSteps} / {progressSteps.length} étapes achevées
            </DialogDescription>
          </DialogHeader>
          {progressSteps.length > 0 && (
            <ol className="flex flex-col gap-2 mt-2">
              {progressSteps.map((step, i) => (
                <li
                  key={i}
                  className={cn(
                    "flex items-start gap-3 rounded-lg border px-3 py-2.5 text-sm",
                    step.status === "running" && "border-primary bg-primary/5",
                    step.status === "done" && "border-success/40 bg-success-muted",
                    step.status === "error" && "border-destructive bg-destructive/5",
                    step.status === "pending" && "border-border bg-muted/30 opacity-60"
                  )}
                >
                  <span className="mt-0.5 shrink-0">
                    {step.status === "done" && <CheckCircle2 className="h-4 w-4 text-success" />}
                    {step.status === "running" && <Loader2 className="h-4 w-4 animate-spin text-primary" />}
                    {step.status === "error" && <AlertCircle className="h-4 w-4 text-destructive" />}
                    {step.status === "pending" && <div className="h-4 w-4 rounded-full border-2 border-muted-foreground/30" />}
                  </span>
                  <div>
                    <p className="font-medium">{step.label}</p>
                    {step.message && <p className="text-xs text-muted-foreground mt-0.5">{step.message}</p>}
                    <Badge variant="muted" className="mt-1 text-xs">{STATUS_LABELS[step.status ?? "pending"] ?? step.status}</Badge>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </DialogContent>
      </Dialog>

      {/* Post-generation progress summary */}
      {!isGenerating && progressSteps.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Dernière génération — {completedSteps}/{progressSteps.length} étapes</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-col gap-2">
              {progressSteps.map((step, i) => (
                <li key={i} className={cn(
                  "flex items-center gap-2 text-sm",
                  step.status === "done" && "text-success",
                  step.status === "error" && "text-destructive"
                )}>
                  {step.status === "done" && <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />}
                  {step.status === "error" && <AlertCircle className="h-3.5 w-3.5 shrink-0" />}
                  {step.status === "running" && <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />}
                  {step.status === "pending" && <div className="h-3.5 w-3.5 rounded-full border border-muted-foreground/30 shrink-0" />}
                  <span>{step.label}</span>
                  {step.message && <span className="text-muted-foreground text-xs">— {step.message}</span>}
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ScenarioCard({
  scenario, displayIndex, isSelected, onSelect
}: {
  scenario: Record<string, unknown>;
  displayIndex: number;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const [showSourcing, setShowSourcing] = useState(false);
  const [showTags, setShowTags] = useState(false);

  const raw = scenario;
  const payload = (raw.scenario ?? raw) as Record<string, unknown>;
  const scenarioTitle = typeof payload.titre === "string" && payload.titre.trim() ? payload.titre.trim() : "";
  const heading = scenarioTitle ? `Scénario ${displayIndex} — ${scenarioTitle}` : `Scénario ${displayIndex}`;
  const axe = payload.axe_narratif as string | undefined;
  const angle = payload.angle_scenarisation as string | undefined;
  const ton = payload.ton as string | undefined;
  const parties = Array.isArray(payload.parties) ? payload.parties : [];
  const sources: string[] =
    (payload.metadata as Record<string, unknown> | undefined)
      ?.coherence_historique as unknown as string[] ?? [];

  const taggedOutput = raw.taggedOutput as Record<string, unknown> | undefined;
  const taggedParties = Array.isArray(taggedOutput?.parties) ? taggedOutput.parties as Array<{ partie_id: unknown; titre: string; taggedText: string }> : [];
  const hasTaggedText = taggedParties.length > 0;

  const sourcingByPart = Array.isArray(parties)
    ? parties.map((part: Record<string, unknown>, idx: number) => {
        const sentences: SentenceSourcing[] = Array.isArray(part?.sentence_sources)
          ? (part.sentence_sources as unknown[]).map((item: unknown) => {
              if (!item || typeof item !== "object") return null;
              const it = item as Record<string, unknown>;
              if (typeof it.sentence !== "string") return null;
              const rawSources = Array.isArray(it.sources) ? it.sources : [];
              return {
                sentence: it.sentence.trim(),
                sources: (rawSources as unknown[]).filter((s): s is string => typeof s === "string").map((s) => s.trim()).filter(Boolean)
              };
            }).filter(Boolean) as SentenceSourcing[]
          : [];
        return { title: (part?.titre as string) || `Partie ${idx + 1}`, sentences };
      }).filter((e) => e.sentences.length > 0)
    : [];
  const hasSourcing = sourcingByPart.length > 0;

  return (
    <Card className={cn("transition-all", isSelected && "border-primary shadow-md ring-1 ring-primary/30")}>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1.5">
            <CardTitle className="text-base">{heading}</CardTitle>
            <div className="flex flex-wrap gap-2">
              {axe && <Badge variant="secondary" className="text-xs gap-1"><BarChart2 className="h-2.5 w-2.5" />{axe}</Badge>}
              {angle && <Badge variant="secondary" className="text-xs gap-1"><BookOpen className="h-2.5 w-2.5" />{ANGLE_LABELS[angle] ?? angle}</Badge>}
              {ton && <Badge variant="secondary" className="text-xs gap-1"><Mic2 className="h-2.5 w-2.5" />{ton}</Badge>}
            </div>
          </div>
          {isSelected && (
            <Badge variant="success" className="shrink-0">
              <CheckCircle2 className="mr-1 h-3 w-3" /> Sélectionné
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {/* Narrative text */}
        <div className="text-sm leading-relaxed max-h-72 overflow-y-auto rounded-lg bg-muted/30 p-3">
          {parties.length > 0 ? (
            showTags && hasTaggedText
              ? taggedParties.map((tp, i) => (
                  <div key={i} className="mb-3">
                    {tp.titre && <p className="font-semibold mb-1">{tp.titre}</p>}
                    {tp.taggedText && <pre className="whitespace-pre-wrap font-mono text-xs">{tp.taggedText}</pre>}
                  </div>
                ))
              : (parties as Array<Record<string, unknown>>).map((part, i) => (
                  <div key={i} className="mb-3">
                    {part.titre ? <p className="font-semibold mb-1">{String(part.titre)}</p> : null}
                    {part.texte_narration ? <p>{String(part.texte_narration)}</p> : null}
                  </div>
                ))
          ) : (
            typeof payload.texte === "string" && <p>{payload.texte}</p>
          )}
        </div>

        {/* Sources */}
        {Array.isArray(sources) && sources.length > 0 && (
          <details className="text-sm">
            <summary className="cursor-pointer text-xs font-medium text-primary">
              Sources ({sources.length})
            </summary>
            <ul className="mt-1.5 list-disc pl-4 space-y-0.5">
              {sources.map((src, i) => <li key={i} className="text-xs text-muted-foreground">{src}</li>)}
            </ul>
          </details>
        )}

        {/* Sourcing panel */}
        {hasSourcing && showSourcing && (
          <div className="rounded-lg border border-primary/20 bg-info-muted/80 p-3 text-sm">
            {sourcingByPart.map((part, i) => (
              <div key={i} className="mb-3 last:mb-0">
                <p className="font-semibold mb-1.5">{part.title}</p>
                <ul className="space-y-2">
                  {part.sentences.map((item, j) => (
                    <li key={j}>
                      <p className="italic text-xs">{item.sentence}</p>
                      {item.sources.length > 0 ? (
                        <div className="flex flex-wrap gap-1 mt-0.5">
                          {item.sources.map((src, k) => (
                            <span key={k} className="text-xs bg-secondary text-info-foreground rounded-full px-2 py-0.5">{src}</span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">Aucune source citée</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between gap-2 pt-1 flex-wrap">
          <div className="flex gap-2">
            {hasSourcing && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowSourcing((p) => !p)}>
                <Tag className="mr-1.5 h-3.5 w-3.5" />
                {showSourcing ? "Masquer sourcing" : "Voir sourcing"}
              </Button>
            )}
            {hasTaggedText && (
              <Button type="button" variant="ghost" size="sm" onClick={() => setShowTags((p) => !p)}>
                {showTags ? "Texte brut" : "Balises TTS"}
              </Button>
            )}
          </div>
          <Button
            type="button"
            variant={isSelected ? "secondary" : "default"}
            size="sm"
            onClick={onSelect}
          >
            {isSelected ? <><CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />Sélectionné</> : "Choisir ce scénario"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
