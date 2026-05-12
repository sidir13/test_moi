import { type DragEvent, type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Upload, Music, Bot, Play, Loader2, ChevronRight,
  CheckCircle2, Circle, Tag
} from "lucide-react";

import {
  advanceStep,
  uploadAudio,
  fetchBackgroundSounds,
  type BackgroundSound,
  uploadBackgroundSound,
  fetchProjectAudio,
  fetchAudioSelection,
  saveAudioSelection,
  fetchProjectProfile,
  type BackgroundSelection,
  fetchVoicePreview
} from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const ELEVEN_LABS_VOICES: { id: string; name: string; descriptor: string }[] = [
  { id: "5l4ttmr4SKNgi0HnOelT", name: "Paul K", descriptor: "Deep French Narrator – Confident, middle-aged, FR" },
  { id: "flHkNRp1BlvT73UL6gyz", name: "Jessica Anne Bogart", descriptor: "Character & Animation – Crisp, middle-aged, US" },
  { id: "jK7dAsiVAhbApIS8KkWB", name: "Vincent (JC)", descriptor: "Smooth, classy, middle-aged, FR" },
  { id: "NOpBlnGInO9m6vDvFkFC", name: "Grandpa Spuds Oxley", descriptor: "Friendly grandpa – Gentle, older, US" },
  { id: "jUHQdLfy668sllNiNTSW", name: "Clément", descriptor: "Top Voice France – Calm, middle-aged, FR" },
  { id: "tKaoyJLW05zqV0tIH9FD", name: "Gaëlle", descriptor: "Audiobooks & Storytelling – Warm, middle-aged, FR" },
  { id: "T4BwQ2ZwlS2BbHIfci4H", name: "Souni", descriptor: "Gentle French female – Calm, young, FR" },
  { id: "GYzIdoKkRyANjBvkKYfO", name: "Koraly", descriptor: "Smooth & Captivating – Pro voice clone, FR" },
  { id: "TojRWZatQyy9dujEdiQ1", name: "Koraly (Storyteller)", descriptor: "Storyteller – Audiobook-tuned, FR" },
];

const formatDuration = (seconds?: number) => {
  if (seconds == null) return null;
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return mins > 0 ? `${mins}:${secs.toString().padStart(2, "0")}` : `${secs}s`;
};

export function AudioSelectionView() {
  const { sessionId, projectName, setCurrentStep, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [file, setFile] = useState<File | null>(null);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const [selectedAmbient, setSelectedAmbient] = useState<string | null>(null);
  const [selectedPunctual, setSelectedPunctual] = useState<string[]>([]);
  const [autoBackgrounds, setAutoBackgrounds] = useState(false);
  const [selectedVoices, setSelectedVoices] = useState<string[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string | null>(null);
  const [voicePreviewUrls, setVoicePreviewUrls] = useState<Record<string, string>>({});
  const [voicePreviewLoading, setVoicePreviewLoading] = useState<Record<string, boolean>>({});
  const [voicePreviewErrors, setVoicePreviewErrors] = useState<Record<string, string | null>>({});
  const [backgroundTitle, setBackgroundTitle] = useState("");
  const [backgroundFile, setBackgroundFile] = useState<File | null>(null);
  const [backgroundStatus, setBackgroundStatus] = useState<string | null>(null);
  const [nextStatus, setNextStatus] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const hiddenBgInput = useRef<HTMLInputElement | null>(null);
  const voicesRef = useRef<string[]>([]);
  const voicePreviewUrlsRef = useRef<Record<string, string>>({});

  const { data: backgroundSounds } = useQuery<BackgroundSound[]>({ queryKey: ["background-sounds"], queryFn: () => fetchBackgroundSounds() });
  const { data: projectAudio } = useQuery({
    queryKey: ["project-audio", projectName],
    queryFn: () => fetchProjectAudio(projectName!),
    enabled: Boolean(projectName)
  });
  const profileQuery = useQuery({
    queryKey: ["project-profile", projectName],
    queryFn: () => fetchProjectProfile(projectName!),
    enabled: Boolean(projectName)
  });
  const selectionQuery = useQuery({
    queryKey: ["audio-selection", sessionId],
    queryFn: () => fetchAudioSelection(sessionId!),
    enabled: Boolean(sessionId)
  });

  const ttsProvider = profileQuery.data?.tts_provider === "qwen" ? "qwen" : "elevenlabs";

  const saveSelection = useMutation({
    mutationFn: (payload: { voices: string[]; backgrounds: BackgroundSelection; auto_backgrounds?: boolean; tts_voice_id?: string | null }) =>
      saveAudioSelection(sessionId!, { project_name: projectName!, ...payload }),
    onSuccess: (data) => {
      selectionQuery.refetch();
      if (data.voices.length > 0) updateProgress({ audioReady: true });
    }
  });

  const persist = (voices: string[], backgrounds: BackgroundSelection, voiceId?: string | null, autoFlag = autoBackgrounds) => {
    saveSelection.mutate({ voices, backgrounds, auto_backgrounds: autoFlag, ...(voiceId ? { tts_voice_id: voiceId } : {}) });
  };

  useEffect(() => {
    if (!selectionQuery.data) return;
    const bg = selectionQuery.data.backgrounds || { ambient: null, punctual: [] };
    setSelectedAmbient(bg.ambient ?? null);
    setSelectedPunctual(bg.punctual ?? []);
    setAutoBackgrounds(Boolean(selectionQuery.data.auto_backgrounds));
    const voices = selectionQuery.data.voices || [];
    setSelectedVoices(voices);
    voicesRef.current = voices;
    setSelectedVoiceId(selectionQuery.data.tts_voice_id ?? null);
  }, [selectionQuery.data]);

  useEffect(() => {
    if (ttsProvider !== "elevenlabs") setSelectedVoiceId(null);
  }, [ttsProvider]);

  useEffect(() => {
    const handler = () => selectionQuery.refetch();
    window.addEventListener("audio-selection-updated", handler);
    return () => window.removeEventListener("audio-selection-updated", handler);
  }, [selectionQuery]);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ voice_id: string; voice_label?: string; reason?: string }>).detail;
      if (detail?.voice_id) {
        // Mise à jour visuelle immédiate — select_voice a déjà sauvegardé côté serveur
        setSelectedVoiceId(detail.voice_id);
        // Invalider le cache pour resynchronisation en arrière-plan (sans bloquer l'UI)
        queryClient.invalidateQueries({ queryKey: ["audio-selection", sessionId] });
      }
    };
    window.addEventListener("voice-selected", handler);
    return () => window.removeEventListener("voice-selected", handler);
  }, [sessionId, queryClient]);

  useEffect(() => { voicePreviewUrlsRef.current = voicePreviewUrls; }, [voicePreviewUrls]);
  useEffect(() => () => { Object.values(voicePreviewUrlsRef.current).forEach(URL.revokeObjectURL); }, []);

  if (!sessionId || !projectName) {
    return <p className="text-sm text-muted-foreground">Sélectionnez d'abord un projet.</p>;
  }

  const handleUpload = async (evt: FormEvent) => {
    evt.preventDefault();
    if (!file) { setUploadMessage("Choisissez un fichier audio"); return; }
    setUploadMessage("Analyse en cours…");
    const data = await uploadAudio(projectName, file);
    const dur = formatDuration((data.metadata as { duration?: number } | undefined)?.duration);
    setUploadMessage(`Importé${dur ? ` (${dur})` : ""}`);
    setFile(null);
    queryClient.invalidateQueries({ queryKey: ["project-audio", projectName] });
    queryClient.invalidateQueries({ queryKey: ["audio-selection", sessionId] });
  };

  const handleBackgroundUpload = async (evt: FormEvent) => {
    evt.preventDefault();
    if (!backgroundTitle.trim() || !backgroundFile) { setBackgroundStatus("Titre et fichier requis."); return; }
    setBackgroundStatus("Ajout en cours…");
    await uploadBackgroundSound(backgroundTitle.trim(), backgroundFile);
    setBackgroundStatus("Ajouté !");
    setBackgroundTitle("");
    setBackgroundFile(null);
    queryClient.invalidateQueries({ queryKey: ["background-sounds"] });
  };

  const handlePreviewVoice = async (voiceId: string) => {
    setVoicePreviewErrors((p) => ({ ...p, [voiceId]: null }));
    setVoicePreviewLoading((p) => ({ ...p, [voiceId]: true }));
    try {
      const blob = await fetchVoicePreview(voiceId);
      const url = URL.createObjectURL(blob);
      setVoicePreviewUrls((p) => {
        if (p[voiceId]) URL.revokeObjectURL(p[voiceId]);
        return { ...p, [voiceId]: url };
      });
    } catch (err) {
      setVoicePreviewErrors((p) => ({ ...p, [voiceId]: (err as Error).message }));
    } finally {
      setVoicePreviewLoading((p) => ({ ...p, [voiceId]: false }));
    }
  };

  const toggleVoice = (track: string) => {
    setSelectedVoices((prev) => {
      if (prev.includes(track)) {
        const next = prev.filter((p) => p !== track);
        voicesRef.current = next;
        persist(next, { ambient: selectedAmbient, punctual: selectedPunctual }, selectedVoiceId);
        updateProgress({ transcriptionsReviewed: false });
        setSelectionError(null);
        return next;
      }
      if (prev.length >= 3) { setSelectionError("Maximum 3 pistes."); return prev; }
      const next = [...prev, track];
      voicesRef.current = next;
      persist(next, { ambient: selectedAmbient, punctual: selectedPunctual }, selectedVoiceId);
      updateProgress({ transcriptionsReviewed: false });
      setSelectionError(null);
      return next;
    });
  };

  const handleAmbientSelect = (path: string | null) => {
    setSelectionError(null);
    setAutoBackgrounds(false);
    const updatedPunctual = path ? selectedPunctual.filter((p) => p !== path) : selectedPunctual;
    setSelectedPunctual(updatedPunctual);
    setSelectedAmbient(path);
    persist(selectedVoices, { ambient: path, punctual: updatedPunctual }, selectedVoiceId, false);
  };

  const handlePunctualToggle = (path: string) => {
    setSelectionError(null);
    setAutoBackgrounds(false);
    setSelectedPunctual((prev) => {
      if (prev.includes(path)) {
        const next = prev.filter((p) => p !== path);
        persist(selectedVoices, { ambient: selectedAmbient, punctual: next }, selectedVoiceId, false);
        return next;
      }
      if (prev.length >= 2) { setSelectionError("Maximum 2 sons ponctuels."); return prev; }
      const next = [...prev, path];
      persist(selectedVoices, { ambient: selectedAmbient === path ? null : selectedAmbient, punctual: next }, selectedVoiceId, false);
      if (selectedAmbient === path) setSelectedAmbient(null);
      return next;
    });
  };

  const handleAutoToggle = (enabled: boolean) => {
    setSelectionError(null);
    setAutoBackgrounds(enabled);
    if (enabled) {
      persist(selectedVoices, { ambient: null, punctual: [] }, selectedVoiceId, true);
    } else {
      persist(selectedVoices, { ambient: selectedAmbient, punctual: selectedPunctual }, selectedVoiceId, false);
    }
  };

  const goNext = async () => {
    const voices = voicesRef.current;
    if (voices.length === 0) { setSelectionError("Sélectionnez au moins une piste vocale."); return; }
    if (ttsProvider === "elevenlabs" && !selectedVoiceId) { setSelectionError("Sélectionnez une voix ElevenLabs."); return; }
    try {
      setNextStatus("Validation des sources…");
      await advanceStep(sessionId, "audio_sources", {
        files: voices,
        backgrounds: { ambient: selectedAmbient, punctual: selectedPunctual },
        auto_backgrounds: autoBackgrounds,
        tts_voice_id: selectedVoiceId ?? undefined
      });
      updateProgress({ audioReady: true, transcriptionsReviewed: false });
      setCurrentStep("transcription_review");
      navigate("/step/transcription_review");
    } catch (err) {
      setSelectionError((err as Error).message);
    } finally {
      setNextStatus(null);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">Sources audio</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Importez vos pistes vocales et configurez les ambiances sonores.
        </p>
      </div>

      {selectionError && (
        <Alert variant="destructive">
          <AlertDescription>{selectionError}</AlertDescription>
        </Alert>
      )}

      {/* Upload voice */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Upload className="h-4 w-4" />Importer une source vocale</CardTitle>
          <CardDescription>Fichiers audio (interviews, témoignages, ambiances inédites).</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleUpload} className="flex flex-col gap-3">
            <Input
              type="file"
              accept="audio/*"
              className="cursor-pointer"
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setUploadMessage(null); }}
            />
            <div className="flex items-center gap-3">
              <Button type="submit" size="sm" disabled={!file}>
                <Upload className="mr-2 h-3.5 w-3.5" />
                Téléverser
              </Button>
              {uploadMessage && <span className="text-sm text-muted-foreground">{uploadMessage}</span>}
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Voice track selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Music className="h-4 w-4" />
            Pistes vocales
            {selectedVoices.length > 0 && (
              <Badge variant="secondary">{selectedVoices.length} / 3 sélectionnée{selectedVoices.length > 1 ? "s" : ""}</Badge>
            )}
          </CardTitle>
          <CardDescription>Sélectionnez jusqu'à 3 pistes utilisées pour la narration.</CardDescription>
        </CardHeader>
        <CardContent>
          {projectAudio && projectAudio.length > 0 ? (
            <ul className="flex flex-col gap-1.5">
              {projectAudio.map((track) => {
                const isSelected = selectedVoices.includes(track);
                return (
                  <li key={track}>
                    <label
                      className={cn(
                        "flex items-center gap-3 rounded-lg border px-3 py-2.5 cursor-pointer transition-all text-sm",
                        isSelected ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
                      )}
                    >
                      <input
                        type="checkbox"
                        className="sr-only"
                        checked={isSelected}
                        onChange={() => toggleVoice(track)}
                      />
                      <span className={cn("flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
                        isSelected ? "border-primary bg-primary text-primary-foreground" : "border-border"
                      )}>
                        {isSelected && <CheckCircle2 className="h-3 w-3" />}
                      </span>
                      <span className="truncate font-medium">{track}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Aucun fichier importé pour le moment.</p>
          )}
        </CardContent>
      </Card>

      {/* ElevenLabs voice picker */}
      {ttsProvider === "elevenlabs" && (
        <Card>
          <CardHeader>
            <CardTitle>Voix ElevenLabs</CardTitle>
            <CardDescription>Écoutez un extrait et sélectionnez la voix narratrice.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {ELEVEN_LABS_VOICES.map((voice) => {
                const isSelected = selectedVoiceId === voice.id;
                return (
                  <div
                    key={voice.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => { setSelectionError(null); setSelectedVoiceId(voice.id); persist(selectedVoices, { ambient: selectedAmbient, punctual: selectedPunctual }, voice.id); }}
                    onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelectedVoiceId(voice.id); } }}
                    className={cn(
                      "flex flex-col gap-2 rounded-xl border p-3 cursor-pointer transition-all",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      isSelected ? "border-primary bg-primary/5 shadow-sm" : "border-border hover:border-primary/40"
                    )}
                  >
                    <input type="radio" name="voice-choice" checked={isSelected} readOnly className="sr-only" />
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold bg-primary/10 text-primary rounded-full px-2 py-0.5">
                        {voice.name}
                      </span>
                      <span className={cn(
                        "h-3 w-3 rounded-full border-2 transition-colors",
                        isSelected ? "border-primary bg-primary" : "border-muted-foreground/30"
                      )} />
                    </div>
                    <p className="text-[10px] text-muted-foreground leading-tight">{voice.descriptor}</p>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="w-full text-xs"
                      disabled={Boolean(voicePreviewLoading[voice.id])}
                      onClick={(e) => { e.stopPropagation(); handlePreviewVoice(voice.id); }}
                    >
                      {voicePreviewLoading[voice.id] ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Play className="h-3 w-3 mr-1" />
                      )}
                      Écouter
                    </Button>
                    {voicePreviewErrors[voice.id] && (
                      <p className="text-xs text-destructive">{voicePreviewErrors[voice.id]}</p>
                    )}
                    {voicePreviewUrls[voice.id] && (
                      <audio controls src={voicePreviewUrls[voice.id]} preload="none" className="w-full" onClick={(e) => e.stopPropagation()} />
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Background ambiance library */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Music className="h-4 w-4" />
            Bibliothèque d'ambiances
          </CardTitle>
          <CardDescription>1 fond continu (optionnel) + jusqu'à 2 sons ponctuels.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <Label htmlFor="auto-bg" className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-primary" />
              Sélection automatique par l'IA
            </Label>
            <Switch id="auto-bg" checked={autoBackgrounds} onCheckedChange={handleAutoToggle} />
          </div>

          {autoBackgrounds && (
            <div className="flex items-start gap-3 rounded-lg border border-primary/20 bg-info-muted px-4 py-3">
              <Bot className="h-4 w-4 text-info-foreground mt-0.5 shrink-0" />
              <div className="text-sm text-foreground">
                <p className="font-semibold">Sélection automatique activée</p>
                <p className="text-xs mt-0.5">Les ambiances seront choisies automatiquement lors de la génération audio, en fonction du texte du scénario.</p>
              </div>
            </div>
          )}

          {!autoBackgrounds && (
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                name="ambient-choice"
                checked={!selectedAmbient}
                onChange={() => handleAmbientSelect(null)}
                className="accent-primary"
              />
              Aucun fond continu
            </label>
          )}

          <div className="flex flex-col gap-2 max-h-80 overflow-y-auto pr-1">
            {backgroundSounds?.map((sound: BackgroundSound) => {
              const isAmbient = selectedAmbient === sound.path;
              const isPunctual = selectedPunctual.includes(sound.path);
              const isSelected = isAmbient || isPunctual;
              return (
                <div
                  key={sound.path}
                  className={cn(
                    "rounded-lg border p-3 flex flex-col gap-2 transition-all",
                    isSelected ? "border-primary bg-primary/5" : "border-border"
                  )}
                >
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-sm flex-1">{sound.name}</span>
                    {sound.category && (
                      <Badge variant="secondary" className="text-xs">{sound.category}</Badge>
                    )}
                    {sound.duration != null && (
                      <span className="text-xs text-muted-foreground">{formatDuration(sound.duration)}</span>
                    )}
                    <audio controls src={sound.preview} className="h-7" />
                  </div>
                  {sound.description && (
                    <p className="text-xs text-muted-foreground">{sound.description}</p>
                  )}
                  {sound.tags && sound.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {sound.tags.map((tag) => (
                        <span key={tag} className="flex items-center gap-0.5 text-xs bg-secondary rounded-full px-2 py-0.5 text-muted-foreground">
                          <Tag className="h-2.5 w-2.5" />{tag}
                        </span>
                      ))}
                    </div>
                  )}
                  {!autoBackgrounds && (
                    <div className="flex gap-4">
                      <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                        <input type="radio" name="ambient-choice" checked={isAmbient} onChange={() => handleAmbientSelect(sound.path)} className="accent-primary" />
                        Fond continu
                      </label>
                      <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                        <input type="checkbox" checked={isPunctual} onChange={() => handlePunctualToggle(sound.path)} className="accent-primary" />
                        Son ponctuel
                      </label>
                    </div>
                  )}
                </div>
              );
            })}
            {!backgroundSounds?.length && (
              <p className="text-sm text-muted-foreground">Aucun son dans la bibliothèque. Ajoutez-en ci-dessous.</p>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Upload background */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Upload className="h-4 w-4" />Ajouter une ambiance</CardTitle>
          <CardDescription>Contribuez à la bibliothèque partagée.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleBackgroundUpload} className="flex flex-col gap-3">
            <Input
              value={backgroundTitle}
              onChange={(e) => setBackgroundTitle(e.target.value)}
              placeholder="Titre (ex: Quai humide, matin de novembre)"
            />
            <div
              className={cn(
                "flex items-center justify-center rounded-lg border-2 border-dashed px-4 py-6 cursor-pointer transition-colors",
                isDragging ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
              )}
              onDrop={(e: DragEvent<HTMLDivElement>) => {
                e.preventDefault();
                setIsDragging(false);
                const f = e.dataTransfer.files?.[0];
                if (f) { setBackgroundFile(f); setBackgroundStatus(`${f.name}`); }
              }}
              onDragOver={(e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onClick={() => hiddenBgInput.current?.click()}
            >
              <div className="text-center">
                <Upload className="h-6 w-6 mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  {backgroundFile ? backgroundFile.name : "Glissez ou cliquez pour sélectionner"}
                </p>
              </div>
              <input
                ref={hiddenBgInput}
                type="file"
                accept="audio/*"
                hidden
                onChange={(e) => setBackgroundFile(e.target.files?.[0] ?? null)}
              />
            </div>
            <div className="flex items-center gap-3">
              <Button type="submit" size="sm">Ajouter à la bibliothèque</Button>
              {backgroundStatus && <span className="text-sm text-muted-foreground">{backgroundStatus}</span>}
            </div>
          </form>
        </CardContent>
      </Card>

      <Separator />

      <div className="flex items-center gap-3">
        {nextStatus && (
          <span className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {nextStatus}
          </span>
        )}
        <Button onClick={goNext} disabled={!sessionId || Boolean(nextStatus)}>
          Étape suivante
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
