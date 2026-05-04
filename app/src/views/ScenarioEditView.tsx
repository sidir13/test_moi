import { type DragEvent, type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import {
  Save, RefreshCw, Plus, Trash2, Upload, Film, Loader2,
  AlertCircle, CheckCircle2, Volume2, Code2, FileText
} from "lucide-react";

import {
  API_BASE_URL,
  advanceStep,
  fetchSelectedScenario,
  selectScenario,
  fetchScenarioAudio,
  synthesizeScenarioAudio,
  getScenarioAudioUrl,
  fetchScenarioImages,
  uploadScenarioImage,
  deleteScenarioImage,
  reorderScenarioImages,
  fetchSlideshow,
  createSlideshow,
  getScenarioSlideshowUrl
} from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type ScenarioPartDraft = { titre: string; texte_narration: string };
type TaggedPartDraft = { titre: string; taggedText: string };

function extractErrorMessage(err: unknown): string | null {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (typeof err.message === "string") return err.message;
  } else if (err instanceof Error) return err.message;
  return null;
}

function extractScenario(raw: Record<string, unknown>): Record<string, unknown> {
  if (raw?.scenario && typeof raw.scenario === "object") return raw.scenario as Record<string, unknown>;
  return raw;
}

function buildUpdatedScenario(
  original: Record<string, unknown>,
  title: string,
  parts: ScenarioPartDraft[],
  freeText: string,
  taggedParts: TaggedPartDraft[] = []
): Record<string, unknown> {
  const base = { ...original };
  const target = (base.scenario && typeof base.scenario === "object")
    ? { ...(base.scenario as Record<string, unknown>) }
    : { ...base };
  target.titre = title;
  if (parts.length > 0) {
    target.parties = parts.map((part, idx) => ({
      titre: part.titre || `Partie ${idx + 1}`,
      texte_narration: part.texte_narration ?? ""
    }));
    delete target.texte;
    delete target.texte_narration;
  } else {
    delete target.parties;
    target.texte_narration = freeText;
  }
  let updated: Record<string, unknown>;
  if (base.scenario && typeof base.scenario === "object") {
    updated = { ...base, scenario: target };
  } else {
    updated = target;
  }
  if (taggedParts.length > 0 && base.taggedOutput && typeof base.taggedOutput === "object") {
    const taggedBase = base.taggedOutput as Record<string, unknown>;
    updated = {
      ...updated,
      taggedOutput: {
        ...taggedBase,
        parties: taggedParts.map((tp, idx) => ({
          ...(Array.isArray(taggedBase.parties) ? ((taggedBase.parties as unknown[])[idx] ?? {}) : {}),
          titre: tp.titre || `Partie ${idx + 1}`,
          taggedText: tp.taggedText ?? ""
        }))
      }
    };
  }
  return updated;
}

export function ScenarioEditView() {
  const { sessionId, setCurrentStep, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [title, setTitle] = useState("");
  const [partsDraft, setPartsDraft] = useState<ScenarioPartDraft[]>([]);
  const [taggedPartsDraft, setTaggedPartsDraft] = useState<TaggedPartDraft[]>([]);
  const [showTags, setShowTags] = useState(false);
  const [freeText, setFreeText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [audioStatus, setAudioStatus] = useState<string | null>(null);
  const [imageStatus, setImageStatus] = useState<string | null>(null);
  const [videoStatus, setVideoStatus] = useState<string | null>(null);
  const [isDraggingFiles, setIsDraggingFiles] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const selectionQuery = useQuery({
    queryKey: ["selected-scenario", sessionId],
    queryFn: () => fetchSelectedScenario(sessionId!),
    enabled: Boolean(sessionId)
  });
  const audioQuery = useQuery({
    queryKey: ["scenario-audio", sessionId],
    queryFn: () => fetchScenarioAudio(sessionId!),
    enabled: Boolean(sessionId)
  });
  const imagesQuery = useQuery({
    queryKey: ["scenario-images", sessionId],
    queryFn: () => fetchScenarioImages(sessionId!),
    enabled: Boolean(sessionId)
  });
  const slideshowQuery = useQuery({
    queryKey: ["scenario-slideshow", sessionId],
    queryFn: () => fetchSlideshow(sessionId!),
    enabled: Boolean(sessionId)
  });

  useEffect(() => {
    if (!selectionQuery.data) return;
    const raw = selectionQuery.data as Record<string, unknown>;
    const payload = extractScenario(raw);
    setTitle((payload.titre as string) ?? "");
    if (Array.isArray(payload.parties) && payload.parties.length > 0) {
      setPartsDraft((payload.parties as Array<Record<string, unknown>>).map((part, idx) => ({
        titre: (part?.titre as string) ?? `Partie ${idx + 1}`,
        texte_narration: ((part?.texte_narration ?? part?.texte) as string) ?? ""
      })));
      setFreeText("");
    } else {
      setPartsDraft([]);
      setFreeText(((payload.texte_narration ?? payload.texte) as string) ?? "");
    }
    const taggedParties = (raw?.taggedOutput as Record<string, unknown> | undefined)?.parties;
    if (Array.isArray(taggedParties) && taggedParties.length > 0) {
      setTaggedPartsDraft((taggedParties as Array<Record<string, unknown>>).map((tp, idx) => ({
        titre: (tp?.titre as string) ?? `Partie ${idx + 1}`,
        taggedText: (tp?.taggedText as string) ?? ""
      })));
    } else {
      setTaggedPartsDraft([]);
    }
  }, [selectionQuery.data]);

  const audioJobStatus = audioQuery.data?.status;
  const isAudioProcessing = audioJobStatus === "pending" || audioJobStatus === "running";
  const hasAudioError = audioJobStatus === "failed";
  const audioReady = audioJobStatus === "done" && Boolean(audioQuery.data?.path);

  useEffect(() => {
    if (!sessionId || !isAudioProcessing) return;
    const interval = setInterval(() => audioQuery.refetch(), 4000);
    return () => clearInterval(interval);
  }, [sessionId, isAudioProcessing, audioQuery]);

  useEffect(() => {
    if (isAudioProcessing) setAudioStatus("Audio en cours de génération…");
    else if (hasAudioError) setAudioStatus(audioQuery.data?.error ? `Échec : ${audioQuery.data.error}` : "Génération impossible.");
    else if (audioJobStatus === "done") setAudioStatus(null);
  }, [audioJobStatus, isAudioProcessing, hasAudioError, audioQuery.data?.error]);

  const audioSrc = useMemo(() => {
    if (!sessionId || !audioReady || !audioQuery.data?.path) return null;
    const base = getScenarioAudioUrl(sessionId).replace(/\/$/, "");
    const ts = audioQuery.data.generated_at ? `?ts=${encodeURIComponent(audioQuery.data.generated_at)}` : "";
    return `${base}${ts}`;
  }, [audioQuery.data, sessionId, audioReady]);

  const slideshowSrc = useMemo(() => {
    if (!sessionId || !slideshowQuery.data?.path) return null;
    const base = getScenarioSlideshowUrl(sessionId).replace(/\/$/, "");
    const ts = slideshowQuery.data.created_at ? `?ts=${encodeURIComponent(slideshowQuery.data.created_at)}` : "";
    return `${base}${ts}`;
  }, [sessionId, slideshowQuery.data]);

  const images = imagesQuery.data ?? [];
  const imagesLimitReached = images.length >= 10;
  const apiBase = useMemo(() => (API_BASE_URL || "").replace(/\/$/, ""), []);
  const hasTaggedText = taggedPartsDraft.length > 0;

  if (!sessionId) return <p className="text-sm text-muted-foreground">Démarrez une session.</p>;
  if (selectionQuery.isLoading) return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />Chargement du scénario…
    </div>
  );
  if (!selectionQuery.data) return <p className="text-sm text-muted-foreground">Aucun scénario sélectionné. Retournez à l'étape précédente.</p>;

  const persistScenario = async () => {
    if (!sessionId || !selectionQuery.data) return;
    const updated = buildUpdatedScenario(selectionQuery.data as Record<string, unknown>, title, partsDraft, freeText, taggedPartsDraft);
    await selectScenario(sessionId, updated);
    await queryClient.invalidateQueries({ queryKey: ["selected-scenario", sessionId] });
  };

  const regenerateAudio = async () => {
    if (!sessionId) return;
    setAudioStatus("Génération d'un nouvel audio…");
    await persistScenario();
    try {
      const job = await synthesizeScenarioAudio(sessionId);
      if (job?.status && job.status !== "done") setAudioStatus("Audio en cours de génération…");
      else setAudioStatus(null);
      await audioQuery.refetch();
    } catch (err) {
      setAudioStatus(extractErrorMessage(err) ?? "Impossible de régénérer l'audio.");
    }
  };

  const handleUploadImages = async (files: FileList | null) => {
    if (!sessionId || !files) return;
    setImageStatus("Téléversement en cours…");
    try {
      for (const file of Array.from(files)) {
        if ((imagesQuery.data?.length ?? 0) >= 10) break;
        await uploadScenarioImage(sessionId, file);
      }
      await imagesQuery.refetch();
      setImageStatus("Images ajoutées.");
    } catch {
      setImageStatus("Impossible d'ajouter les images.");
    }
  };

  const handleCreateSlideshow = async () => {
    if (images.length === 0) { setVideoStatus("Ajoutez des images d'abord."); return; }
    if (!audioQuery.data?.path) { setVideoStatus("Générez l'audio avant le diaporama."); return; }
    setVideoStatus("Création du diaporama…");
    try {
      await createSlideshow(sessionId!);
      await slideshowQuery.refetch();
      setVideoStatus("Diaporama créé.");
    } catch (err) {
      setVideoStatus(extractErrorMessage(err) ?? "Création impossible.");
    }
  };

  const handleDropFiles = async (evt: DragEvent<HTMLDivElement>) => {
    evt.preventDefault();
    setIsDraggingFiles(false);
    if (!imagesLimitReached && evt.dataTransfer.files.length > 0) {
      await handleUploadImages(evt.dataTransfer.files);
      evt.dataTransfer.clearData();
    }
  };

  const handleDragStart = (evt: DragEvent<HTMLDivElement>, id: string) => {
    evt.dataTransfer.setData("text/plain", id);
  };

  const handleDropOnImage = async (evt: DragEvent<HTMLDivElement>, targetId: string) => {
    evt.preventDefault();
    const fromId = evt.dataTransfer.getData("text/plain");
    if (fromId && fromId !== targetId && sessionId && imagesQuery.data) {
      const list = [...imagesQuery.data];
      const fromIdx = list.findIndex((i) => i.id === fromId);
      const toIdx = list.findIndex((i) => i.id === targetId);
      if (fromIdx !== -1 && toIdx !== -1) {
        const reordered = [...list];
        const [moved] = reordered.splice(fromIdx, 1);
        reordered.splice(toIdx, 0, moved);
        await reorderScenarioImages(sessionId, reordered.map((i) => i.id));
        await imagesQuery.refetch();
      }
    }
  };

  const handleSubmit = async (evt: FormEvent) => {
    evt.preventDefault();
    setStatus("Sauvegarde en cours…");
    await persistScenario();
    const refreshed = await audioQuery.refetch();
    if (!refreshed.data?.path) {
      setStatus("Générez l'audio avant de passer à la validation finale.");
      return;
    }
    if ((imagesQuery.data?.length ?? 0) > 0 && audioQuery.data?.path && !slideshowQuery.data?.path) {
      await createSlideshow(sessionId!).catch(() => {});
    }
    await advanceStep(sessionId, "scenario_edit", { titre: title });
    updateProgress({ scenarioEdited: true });
    setCurrentStep("final_validation");
    navigate("/step/final_validation");
  };

  const scenarioTitle = title?.trim();
  const heading = scenarioTitle ? `Modifier le scénario — ${scenarioTitle}` : "Modifier le scénario";

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">{heading}</h2>
          <p className="text-sm text-muted-foreground mt-1">Affinez le texte, réécoutez et validez votre scénario.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        {/* Scenario title */}
        <Card>
          <CardHeader>
            <CardTitle>Titre du scénario</CardTitle>
          </CardHeader>
          <CardContent>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Titre du scénario" />
          </CardContent>
        </Card>

        {/* Narrative structure */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Structure narrative</CardTitle>
                <CardDescription>Éditez les parties du scénario.</CardDescription>
              </div>
              {hasTaggedText && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowTags((p) => !p)}
                >
                  {showTags ? <><FileText className="mr-1.5 h-3.5 w-3.5" />Texte brut</> : <><Code2 className="mr-1.5 h-3.5 w-3.5" />Balises ElevenLabs</>}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {showTags && hasTaggedText ? (
              <>
                <p className="text-xs text-muted-foreground">
                  Texte balisé envoyé à ElevenLabs. Les balises <code className="rounded bg-muted px-1">[pause]</code>, <code className="rounded bg-muted px-1">[posé]</code>, etc. seront interprétées par le moteur vocal.
                </p>
                {taggedPartsDraft.map((tp, idx) => (
                  <div key={idx} className="flex flex-col gap-2 rounded-lg border border-border p-3">
                    <p className="text-sm font-semibold">{tp.titre || `Partie ${idx + 1}`}</p>
                    <Textarea
                      rows={8}
                      value={tp.taggedText}
                      className="font-mono text-xs"
                      onChange={(e) => setTaggedPartsDraft((prev) => prev.map((p, i) => i === idx ? { ...p, taggedText: e.target.value } : p))}
                    />
                  </div>
                ))}
              </>
            ) : partsDraft.length === 0 ? (
              <>
                <Textarea rows={12} value={freeText} onChange={(e) => setFreeText(e.target.value)} placeholder="Corps du scénario…" />
                <Button type="button" variant="outline" size="sm" className="w-fit" onClick={() => { setPartsDraft([{ titre: "Partie 1", texte_narration: freeText }]); setFreeText(""); }}>
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                  Découper en parties
                </Button>
              </>
            ) : (
              <>
                {partsDraft.map((part, idx) => (
                  <div key={idx} className="flex flex-col gap-2 rounded-lg border border-border p-3">
                    <div className="flex items-center justify-between gap-2">
                      <Label className="text-xs text-muted-foreground">Titre de la partie</Label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 text-destructive hover:text-destructive"
                        onClick={() => setPartsDraft((prev) => prev.filter((_, i) => i !== idx))}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                    <Input
                      value={part.titre}
                      onChange={(e) => setPartsDraft((prev) => prev.map((p, i) => i === idx ? { ...p, titre: e.target.value } : p))}
                      placeholder={`Partie ${idx + 1}`}
                    />
                    <Textarea
                      rows={5}
                      value={part.texte_narration}
                      onChange={(e) => setPartsDraft((prev) => prev.map((p, i) => i === idx ? { ...p, texte_narration: e.target.value } : p))}
                      placeholder="Texte de narration…"
                    />
                  </div>
                ))}
                <Button type="button" variant="outline" size="sm" className="w-fit" onClick={() => setPartsDraft((prev) => [...prev, { titre: `Partie ${prev.length + 1}`, texte_narration: "" }])}>
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                  Ajouter une partie
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        {/* Audio preview */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Volume2 className="h-4 w-4" />
              Pré-écoute audio
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {audioQuery.isFetching && !audioSrc && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />Chargement…
              </div>
            )}
            {isAudioProcessing && (
              <div className="flex items-center gap-2 text-sm text-primary">
                <Loader2 className="h-4 w-4 animate-spin" />Audio en cours de génération…
              </div>
            )}
            {hasAudioError && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{audioQuery.data?.error ?? "Génération impossible."}</AlertDescription>
              </Alert>
            )}
            {audioSrc && (
              <>
                <audio controls src={audioSrc} preload="auto" className="w-full rounded-lg" />
                {audioQuery.data?.generated_at && (
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                    Généré le {new Date(audioQuery.data.generated_at).toLocaleString()}
                  </p>
                )}
              </>
            )}
            {!audioSrc && !audioQuery.isFetching && !isAudioProcessing && (
              <p className="text-sm text-muted-foreground">Aucun audio disponible.</p>
            )}
            {audioStatus && (
              <p className="text-sm text-muted-foreground">{audioStatus}</p>
            )}
            <Button type="button" variant="outline" size="sm" className="w-fit" onClick={regenerateAudio} disabled={isAudioProcessing}>
              <RefreshCw className={cn("mr-1.5 h-3.5 w-3.5", isAudioProcessing && "animate-spin")} />
              Régénérer l'audio
            </Button>
          </CardContent>
        </Card>

        {/* Images & slideshow */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Film className="h-4 w-4" />
              Images & diaporama
              <Badge variant="secondary" className="text-xs">{images.length} / 10</Badge>
            </CardTitle>
            <CardDescription>Ajoutez jusqu'à 10 images, réorganisez par glisser-déposer, puis générez un diaporama synchronisé.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(e) => { handleUploadImages(e.target.files); e.target.value = ""; }}
            />
            <div
              role="button"
              tabIndex={0}
              aria-disabled={imagesLimitReached}
              onClick={() => !imagesLimitReached && fileInputRef.current?.click()}
              onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !imagesLimitReached) { e.preventDefault(); fileInputRef.current?.click(); } }}
              onDragEnter={(e) => { e.preventDefault(); if (!imagesLimitReached) setIsDraggingFiles(true); }}
              onDragOver={(e) => { e.preventDefault(); if (!imagesLimitReached) setIsDraggingFiles(true); }}
              onDragLeave={(e) => { e.preventDefault(); setIsDraggingFiles(false); }}
              onDrop={handleDropFiles}
              className={cn(
                "flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors",
                isDraggingFiles ? "border-primary bg-primary/5" : "border-border hover:border-primary/50",
                imagesLimitReached && "cursor-not-allowed opacity-50"
              )}
            >
              <Upload className="h-6 w-6 mb-2 text-muted-foreground" />
              <p className="text-sm font-medium">
                {imagesLimitReached ? "Limite atteinte (10 images)" : "Déposez vos visuels ici"}
              </p>
              {!imagesLimitReached && (
                <p className="text-xs text-muted-foreground mt-1">Cliquez ou glissez-déposez des JPEG / PNG</p>
              )}
            </div>
            {imageStatus && <p className="text-sm text-muted-foreground">{imageStatus}</p>}

            {images.length > 0 && (
              <div className="flex flex-wrap gap-3">
                {images.map((image) => (
                  <div
                    key={image.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, image.id)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => handleDropOnImage(e, image.id)}
                    className="relative h-32 w-32 shrink-0 overflow-hidden rounded-lg border border-border bg-muted cursor-grab active:cursor-grabbing"
                  >
                    <img
                      src={`${apiBase}${image.download_url}`}
                      alt={image.original_name ?? image.filename}
                      className="h-full w-full object-cover"
                    />
                    <Button
                      type="button"
                      variant="destructive"
                      size="icon"
                      className="absolute right-1 top-1 h-6 w-6 rounded-full opacity-80 hover:opacity-100"
                      onClick={() => deleteScenarioImage(sessionId!, image.id).then(() => imagesQuery.refetch())}
                      aria-label="Supprimer"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            )}

            <div className="flex items-center gap-3 flex-wrap">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleCreateSlideshow}
                disabled={images.length === 0}
              >
                <Film className="mr-1.5 h-3.5 w-3.5" />
                Créer le diaporama
              </Button>
              {videoStatus && <span className="text-sm text-muted-foreground">{videoStatus}</span>}
            </div>

            {slideshowSrc && (
              <div className="flex flex-col gap-2">
                <p className="text-sm font-medium">Diaporama généré</p>
                <video controls src={slideshowSrc} className="w-full max-h-80 rounded-lg" />
              </div>
            )}
          </CardContent>
        </Card>

        {status && (
          <Alert variant={status.includes("Générez") ? "warning" : "default"}>
            <AlertDescription>{status}</AlertDescription>
          </Alert>
        )}

        <Separator />
        <div className="flex gap-3">
          <Button type="button" variant="outline" onClick={async () => { setStatus("Sauvegarde…"); await persistScenario(); setStatus("Scénario mis à jour."); setTimeout(() => setStatus(null), 2000); }}>
            <Save className="mr-1.5 h-4 w-4" />
            Sauvegarder le texte
          </Button>
          <Button type="submit">
            Valider l'édition
          </Button>
        </div>
      </form>
    </div>
  );
}
