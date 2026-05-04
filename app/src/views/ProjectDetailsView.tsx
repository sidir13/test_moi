import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Save, ChevronRight } from "lucide-react";

import { advanceStep, fetchProjectProfile } from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

const DEFAULT_DURATION_SECONDS = 120;
const MIN_DURATION_SECONDS = 30;

const formatOptionLabel = (value: string) =>
  value
    .split("_")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");

const formatDuration = (seconds: number) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return [mins > 0 ? `${mins} min` : "", `${secs.toString().padStart(2, "0")} s`]
    .filter(Boolean)
    .join(" ");
};

export function ProjectDetailsView() {
  const { sessionId, projectName, setCurrentStep, setProgress } = useSessionStore();
  const navigate = useNavigate();

  const [notes, setNotes] = useState("");
  const [audience, setAudience] = useState("");
  const [tone, setTone] = useState("");
  const [voiceInstructions, setVoiceInstructions] = useState("");
  const [targetDuration, setTargetDuration] = useState(DEFAULT_DURATION_SECONDS);
  const [ttsProvider, setTtsProvider] = useState<"qwen" | "elevenlabs">("elevenlabs");
  const [includeCitations, setIncludeCitations] = useState(true);
  const [sourceUsageLevel, setSourceUsageLevel] = useState<"leger" | "modere" | "central">("modere");
  const [status, setStatus] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const notesPrefilledFor = useRef<string | null>(null);
  const progressPrefilledFor = useRef<string | null>(null);
  const preferencesPrefilledFor = useRef<string | null>(null);

  const profileQuery = useQuery({
    queryKey: ["project-profile", projectName],
    queryFn: () => fetchProjectProfile(projectName!),
    enabled: Boolean(projectName)
  });

  useEffect(() => {
    if (!projectName) {
      notesPrefilledFor.current = null;
      progressPrefilledFor.current = null;
      preferencesPrefilledFor.current = null;
    }
  }, [projectName]);

  useEffect(() => {
    if (!projectName || !profileQuery.data) return;
    if (notesPrefilledFor.current === projectName) return;
    setNotes(profileQuery.data.project_notes ?? "");
    notesPrefilledFor.current = projectName;
  }, [profileQuery.data, projectName]);

  useEffect(() => {
    if (!projectName || !profileQuery.data) return;
    if (preferencesPrefilledFor.current === projectName) return;
    const pref = profileQuery.data.preference_options;
    const ds = pref?.duration;
    const clamp = (v: number) => (ds ? Math.min(ds.max, Math.max(ds.min, v)) : v);
    setAudience(profileQuery.data.audience ?? "");
    setTone(profileQuery.data.tone ?? "");
    setVoiceInstructions(profileQuery.data.voice_instructions ?? "");
    setTtsProvider(profileQuery.data.tts_provider === "qwen" ? "qwen" : "elevenlabs");
    setIncludeCitations(profileQuery.data.include_citations !== false);
    const savedLevel = profileQuery.data.source_usage_level;
    if (savedLevel === "leger" || savedLevel === "modere" || savedLevel === "central") {
      setSourceUsageLevel(savedLevel);
    }
    const raw =
      profileQuery.data.target_duration ?? ds?.default ?? DEFAULT_DURATION_SECONDS;
    setTargetDuration(clamp(typeof raw === "number" ? raw : DEFAULT_DURATION_SECONDS));
    preferencesPrefilledFor.current = projectName;
  }, [profileQuery.data, projectName]);

  useEffect(() => {
    if (!projectName || !profileQuery.data) return;
    if (progressPrefilledFor.current === projectName) return;
    const hasStored = Boolean(profileQuery.data.last_scenarios?.length);
    const hasFinal = Boolean(profileQuery.data.final_scenario);
    setProgress({
      audioReady: Boolean(
        profileQuery.data.final_audio?.path || profileQuery.data.audio_selection?.voices?.length
      ),
      transcriptionsReviewed:
        Boolean(profileQuery.data.final_audio?.path) || hasStored || hasFinal,
      scenariosReady: hasStored || hasFinal,
      scenarioChosen: hasFinal,
      scenarioEdited: false
    });
    progressPrefilledFor.current = projectName;
  }, [profileQuery.data, projectName, setProgress]);

  const preferenceOptions = profileQuery.data?.preference_options;
  const toneOptions = preferenceOptions?.tone_options ?? [];
  const audienceOptions = preferenceOptions?.audience_options ?? [];

  const durationSettings = useMemo(() => {
    const configuredMin = preferenceOptions?.duration?.min;
    const enforcedMin = Math.min(
      typeof configuredMin === "number" ? configuredMin : MIN_DURATION_SECONDS,
      MIN_DURATION_SECONDS
    );
    return {
      min: enforcedMin,
      max: preferenceOptions?.duration?.max ?? 600,
      step: preferenceOptions?.duration?.step ?? 10
    };
  }, [preferenceOptions]);

  const sliderRangeLabel = useMemo(() => {
    const fmt = (v: number) => (v % 60 === 0 ? `${v / 60} min` : `${v}s`);
    return `${fmt(durationSettings.min)} – ${fmt(durationSettings.max)}`;
  }, [durationSettings]);

  if (!sessionId) {
    return <p className="text-sm text-muted-foreground">Créez ou sélectionnez un projet pour continuer.</p>;
  }

  const handleSubmit = async (evt: FormEvent) => {
    evt.preventDefault();
    setIsSaving(true);
    setStatus(null);
    try {
      await advanceStep(sessionId, "project_details", {
        notes,
        audience: audience || undefined,
        tone: tone || undefined,
        target_duration: targetDuration,
        voice_instructions: voiceInstructions?.trim() || undefined,
        tts_provider: ttsProvider,
        include_citations: includeCitations,
        source_usage_level: sourceUsageLevel
      });
      setCurrentStep("audio_sources");
      navigate("/step/audio_sources");
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Détails du projet</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Contexte, public cible, ton et paramètres vocaux.
          </p>
        </div>
        {profileQuery.isFetching && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            Chargement…
          </div>
        )}
      </div>

      {status && (
        <Alert variant="destructive">
          <AlertDescription>{status}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <Card>
          <CardHeader>
            <CardTitle>Contexte narratif</CardTitle>
            <CardDescription>Décrivez l'histoire à raconter. Les agents IA s'appuieront sur ce texte.</CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={6}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Quelle histoire souhaitez-vous raconter ? Quelle période, quel territoire, quels événements ?"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Public & ton narratif</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label>Public cible</Label>
              <Select value={audience} onValueChange={setAudience}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionner…" />
                </SelectTrigger>
                <SelectContent>
                  {audienceOptions.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {formatOptionLabel(opt)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Ton narratif</Label>
              <Select value={tone} onValueChange={setTone}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionner…" />
                </SelectTrigger>
                <SelectContent>
                  {toneOptions.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {formatOptionLabel(opt)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Durée audio ciblée</CardTitle>
          </CardHeader>
          <CardContent>
            <Slider
              label="Durée"
              valueLabel={formatDuration(targetDuration)}
              hint={`Entre ${sliderRangeLabel}`}
              min={durationSettings.min}
              max={durationSettings.max}
              step={durationSettings.step}
              value={targetDuration}
              onChange={(e) => setTargetDuration(Number(e.target.value))}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Moteur de synthèse vocale</CardTitle>
            <CardDescription>Choisissez la technologie TTS utilisée pour la narration finale.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex items-center gap-4">
              <span className={ttsProvider !== "elevenlabs" ? "font-semibold text-sm" : "text-sm text-muted-foreground"}>
                Qwen local
              </span>
              <Switch
                checked={ttsProvider === "elevenlabs"}
                onCheckedChange={(checked) => setTtsProvider(checked ? "elevenlabs" : "qwen")}
                aria-label="Basculer entre Qwen local et ElevenLabs"
              />
              <span className={ttsProvider === "elevenlabs" ? "font-semibold text-sm" : "text-sm text-muted-foreground"}>
                ElevenLabs
              </span>
              <Badge variant={ttsProvider === "elevenlabs" ? "default" : "secondary"}>
                {ttsProvider === "elevenlabs" ? "Cloud" : "Local"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {ttsProvider === "elevenlabs"
                ? "Voix ElevenLabs hébergées — qualité et expressivité maximales."
                : "Synthèse locale Qwen — aucune dépendance cloud, voix générée d'après vos consignes."}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Consignes vocales</CardTitle>
            <CardDescription>Instructions transmises au moteur TTS pour guider le style de narration.</CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={4}
              value={voiceInstructions}
              onChange={(e) => setVoiceInstructions(e.target.value)}
              placeholder="Ex: Use a female narrator, warm and composed, with slight regional accent…"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sources & citations</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="flex flex-col gap-1.5">
                <Label>Utilisation des sources audio</Label>
                <Select
                  value={sourceUsageLevel}
                  onValueChange={(v) => setSourceUsageLevel(v as "leger" | "modere" | "central")}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="leger">Léger — contexte uniquement</SelectItem>
                    <SelectItem value="modere">Modéré — sourcing équilibré</SelectItem>
                    <SelectItem value="central">Central — élément narratif majeur</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Détermine l'importance des transcriptions dans le récit.
                </p>
              </div>
              <div className="flex flex-col gap-2 justify-center">
                <Label className="flex items-center gap-2 cursor-pointer">
                  <Switch
                    checked={includeCitations}
                    onCheckedChange={setIncludeCitations}
                    id="citations-toggle"
                  />
                  <span>Inclure les citations directes</span>
                </Label>
                <p className="text-xs text-muted-foreground">
                  Autorise le scénariste à citer des extraits des sources.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Separator />

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Sauvegarder & continuer
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
