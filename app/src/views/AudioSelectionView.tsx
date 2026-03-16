import { DragEvent, FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  advanceStep,
  uploadAudio,
  fetchBackgroundSounds,
  BackgroundSound,
  uploadBackgroundSound,
  fetchProjectAudio,
  fetchAudioSelection,
  saveAudioSelection,
  fetchProjectProfile,
  BackgroundSelection,
  fetchVoicePreview
} from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

const formatDuration = (seconds?: number) => {
  if (seconds == null) return "instantané";
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return mins > 0 ? `${mins} min ${secs.toString().padStart(2, "0")} s` : `${secs} s`;
};

const ELEVEN_LABS_VOICE_OPTIONS = [
  { id: "5l4ttmr4SKNgi0HnOelT", label: "Voix 1 — 5l4ttmr4..." },
  { id: "flHkNRp1BlvT73UL6gyz", label: "Voix 2 — flHkNRp1..." },
  { id: "jK7dAsiVAhbApIS8KkWB", label: "Voix 3 — jK7dAsi..." },
  { id: "NOpBlnGInO9m6vDvFkFC", label: "Voix 4 — NOpBlnGI..." },
  { id: "jUHQdLfy668sllNiNTSW", label: "Voix 5 — jUHQdLf..." },
  { id: "tKaoyJLW05zqV0tIH9FD", label: "Voix 6 — tKaoyJL..." },
  { id: "T4BwQ2ZwlS2BbHIfci4H", label: "Voix 7 — T4BwQ2Z..." },
  { id: "GYzIdoKkRyANjBvkKYfO", label: "Voix 8 — GYzIdoK..." },
  { id: "TojRWZatQyy9dujEdiQ1", label: "Voix 9 — TojRWZa..." }
];

export function AudioSelectionView() {
  const { sessionId, projectName, setCurrentStep, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
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
  const hiddenBackgroundInput = useRef<HTMLInputElement | null>(null);
  const voicesRef = useRef<string[]>([]);
  const voicePreviewUrlsRef = useRef<Record<string, string>>({});
  const { data: backgroundSounds } = useQuery({
    queryKey: ["background-sounds"],
    queryFn: () => fetchBackgroundSounds()
  });
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
      if (data.voices.length > 0) {
        updateProgress({ audioReady: true });
      }
    }
  });
  const persistSelection = (
    voices: string[],
    backgrounds: BackgroundSelection,
    voiceId?: string | null,
    autoFlag = autoBackgrounds
  ) => {
    const payload: { voices: string[]; backgrounds: BackgroundSelection; auto_backgrounds?: boolean; tts_voice_id?: string | null } = {
      voices,
      backgrounds,
      auto_backgrounds: autoFlag
    };
    if (voiceId) {
      payload.tts_voice_id = voiceId;
    }
    saveSelection.mutate(payload);
  };

  useEffect(() => {
    if (selectionQuery.data) {
      const backgrounds = selectionQuery.data.backgrounds || { ambient: null, punctual: [] };
      setSelectedAmbient(backgrounds.ambient ?? null);
      setSelectedPunctual(backgrounds.punctual ?? []);
      setAutoBackgrounds(Boolean(selectionQuery.data.auto_backgrounds));
      const voices = selectionQuery.data.voices || [];
      setSelectedVoices(voices);
      voicesRef.current = voices;
      setSelectedVoiceId(selectionQuery.data.tts_voice_id ?? null);
    }
  }, [selectionQuery.data]);
  useEffect(() => {
    if (ttsProvider !== "elevenlabs") {
      setSelectedVoiceId(null);
    }
  }, [ttsProvider]);

  useEffect(() => {
    const handler = () => selectionQuery.refetch();
    window.addEventListener("audio-selection-updated", handler);
    return () => window.removeEventListener("audio-selection-updated", handler);
  }, [selectionQuery]);
  useEffect(() => {
    voicePreviewUrlsRef.current = voicePreviewUrls;
  }, [voicePreviewUrls]);
  useEffect(() => {
    return () => {
      Object.values(voicePreviewUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  if (!sessionId || !projectName) {
    return <p>Sélectionnez d'abord un projet.</p>;
  }

  const handleUpload = async (evt: FormEvent) => {
    evt.preventDefault();
    if (!file) {
      setMessage("Choisissez un fichier audio");
      return;
    }
    setMessage("Analyse en cours...");
    const data = await uploadAudio(projectName, file);
    setMessage(`Fichier importé (${formatDuration(data.metadata?.duration)})`);
    queryClient.invalidateQueries({ queryKey: ["project-audio", projectName] });
    queryClient.invalidateQueries({ queryKey: ["audio-selection", sessionId] });
  };

  const handleBackgroundUpload = async (evt: FormEvent) => {
    evt.preventDefault();
    if (!backgroundTitle.trim() || !backgroundFile) {
      setBackgroundStatus("Ajoutez un titre et un fichier.");
      return;
    }
    setBackgroundStatus("Ajout en cours...");
    await uploadBackgroundSound(backgroundTitle.trim(), backgroundFile);
    setBackgroundStatus("Ajouté à la bibliothèque");
    setBackgroundTitle("");
    setBackgroundFile(null);
    queryClient.invalidateQueries({ queryKey: ["background-sounds"] });
  };

  const handleDrop = (evt: DragEvent<HTMLDivElement>) => {
    evt.preventDefault();
    const dropped = evt.dataTransfer.files?.[0];
    if (dropped) {
      setBackgroundFile(dropped);
      setBackgroundStatus(`Fichier sélectionné : ${dropped.name}`);
    }
  };

  const handleDragOver = (evt: DragEvent<HTMLDivElement>) => {
    evt.preventDefault();
  };

  const handleVoiceIdChange = (value: string) => {
    setSelectionError(null);
    const normalized = value || null;
    setSelectedVoiceId(normalized);
    persistSelection(
      selectedVoices,
      { ambient: selectedAmbient, punctual: selectedPunctual },
      normalized
    );
  };

  const handlePreviewVoice = async (voiceId: string) => {
    setVoicePreviewErrors((prev) => ({ ...prev, [voiceId]: null }));
    setVoicePreviewLoading((prev) => ({ ...prev, [voiceId]: true }));
    try {
      const blob = await fetchVoicePreview(voiceId);
      const url = URL.createObjectURL(blob);
      setVoicePreviewUrls((prev) => {
        const next = { ...prev };
        if (prev[voiceId]) {
          URL.revokeObjectURL(prev[voiceId]);
        }
        next[voiceId] = url;
        return next;
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Impossible de charger l'aperçu.";
      setVoicePreviewErrors((prev) => ({ ...prev, [voiceId]: message }));
    } finally {
      setVoicePreviewLoading((prev) => ({ ...prev, [voiceId]: false }));
    }
  };

  const handleVoiceCardSelect = (voiceId: string) => {
    handleVoiceIdChange(voiceId);
  };

  const handleVoiceCardKeyDown = (voiceId: string, event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleVoiceCardSelect(voiceId);
    }
  };

  const goNext = async () => {
    const voices = voicesRef.current;
    if (voices.length === 0) {
      setSelectionError("Sélectionnez au moins une piste vocale avant de continuer.");
      return;
    }
    if (ttsProvider === "elevenlabs" && !selectedVoiceId) {
      setSelectionError("Sélectionnez une voix ElevenLabs avant de continuer.");
      return;
    }
    try {
      setNextStatus("Validation des sources...");
      await advanceStep(sessionId, "audio_sources", {
        files: voices,
        backgrounds: {
          ambient: selectedAmbient,
          punctual: selectedPunctual
        },
        auto_backgrounds: autoBackgrounds,
        tts_voice_id: selectedVoiceId ?? undefined
      });
      updateProgress({ audioReady: true, transcriptionsReviewed: false });
      setCurrentStep("transcription_review");
      navigate("/step/transcription_review");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Impossible de passer à l'étape suivante.";
      setSelectionError(message);
    } finally {
      setNextStatus(null);
    }
  };

  const currentBackgroundSelection = (): BackgroundSelection => ({
    ambient: selectedAmbient,
    punctual: selectedPunctual
  });

  const toggleVoice = (track: string) => {
    setSelectedVoices((prev) => {
      let next = prev;
      let changed = false;
      if (prev.includes(track)) {
        next = prev.filter((p) => p !== track);
        changed = next !== prev;
      } else if (prev.length >= 3) {
        setSelectionError("Sélectionnez 3 pistes maximum.");
        changed = false;
      } else {
        next = [...prev, track];
        changed = true;
      }
      if (!changed) {
        return prev;
      }
      setSelectionError(null);
      voicesRef.current = next;
      persistSelection(next, currentBackgroundSelection(), selectedVoiceId);
      updateProgress({ transcriptionsReviewed: false });
      return next;
    });
  };

  const handleAmbientSelect = (path: string | null) => {
    setSelectionError(null);
    setAutoBackgrounds(false);
    const updatedPunctual = path ? selectedPunctual.filter((p) => p !== path) : selectedPunctual;
    setSelectedPunctual(updatedPunctual);
    setSelectedAmbient(path);
    persistSelection(selectedVoices, { ambient: path, punctual: updatedPunctual }, selectedVoiceId, false);
  };

  const handlePunctualToggle = (path: string) => {
    setSelectionError(null);
    setAutoBackgrounds(false);
    setSelectedPunctual((prev) => {
      if (prev.includes(path)) {
        const next = prev.filter((p) => p !== path);
        persistSelection(selectedVoices, { ambient: selectedAmbient, punctual: next }, selectedVoiceId, false);
        return next;
      }
      if (prev.length >= 2) {
        setSelectionError("Vous pouvez ajouter au maximum deux sons ponctuels.");
        return prev;
      }
      const next = [...prev, path];
      if (selectedAmbient === path) {
        setSelectedAmbient(null);
      }
      persistSelection(selectedVoices, { ambient: selectedAmbient === path ? null : selectedAmbient, punctual: next }, selectedVoiceId, false);
      return next;
    });
  };

  const handleAutoToggleChange = (enabled: boolean) => {
    setSelectionError(null);
    setAutoBackgrounds(enabled);
    if (enabled) {
      // Sauvegarder le flag auto=true avec une sélection vide.
      // La sélection réelle se fera au moment de la génération audio.
      persistSelection(selectedVoices, { ambient: null, punctual: [] }, selectedVoiceId, true);
    } else {
      // Repasser en manuel : conserver la sélection courante (vide ou non)
      persistSelection(selectedVoices, currentBackgroundSelection(), selectedVoiceId, false);
    }
  };

  return (
    <div className="step-view">
      <h2>Sélection des sources audios</h2>
      <section className="card">
        <h3>Importer de nouvelles sources</h3>
        <p>
          Glissez-déposez vos interviews (ou ambiances inédites) : elles seront copiées dans l'application et pourront
          être analysées immédiatement.
        </p>
        <form onSubmit={handleUpload} className="form-grid">
          <input
            type="file"
            accept="audio/*"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setMessage(null);
            }}
          />
          <button type="submit">Téléverser le fichier</button>
        </form>
        {message && <p>{message}</p>}
      </section>

      <section className="card">
        <h3>Pistes vocales disponibles</h3>
        {projectAudio && projectAudio.length > 0 ? (
          <ul className="project-list">
            {projectAudio.map((track) => (
              <li key={track}>
                <label>
                  <input
                    type="checkbox"
                    checked={selectedVoices.includes(track)}
                    onChange={() => toggleVoice(track)}
                  />
                  {track}
                </label>
              </li>
            ))}
          </ul>
        ) : (
          <p>Aucun fichier importé pour le moment.</p>
        )}
      </section>

      <section className="card">
        <h3>Ajouter une ambiance à la bibliothèque</h3>
        <form onSubmit={handleBackgroundUpload} className="form-grid">
          <label>
            Titre
            <input value={backgroundTitle} onChange={(e) => setBackgroundTitle(e.target.value)} placeholder="Ex: Quai humide" />
          </label>
          <div
            className="drop-zone"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => hiddenBackgroundInput.current?.click()}
          >
            {backgroundFile ? (
              <span>{backgroundFile.name}</span>
            ) : (
              <span>Glissez-déposez ou cliquez pour sélectionner un son d'ambiance</span>
            )}
            <input
              ref={hiddenBackgroundInput}
              type="file"
              accept="audio/*"
              hidden
              onChange={(e) => {
                setBackgroundFile(e.target.files?.[0] ?? null);
              }}
            />
          </div>
          <button type="submit">Ajouter à la bibliothèque</button>
        </form>
        {backgroundStatus && <p>{backgroundStatus}</p>}
      </section>

      <section className="card">
        <h3>Bibliothèque des sons d'ambiance</h3>
        <p>
          Choisissez un fond continu (0 ou 1) et jusqu'à deux sons ponctuels pour rythmer votre narration.
        </p>
        {selectionError && <p className="error">{selectionError}</p>}
        <div className="background-actions-row">
          <label className="toggle-field">
            <input
              type="checkbox"
              checked={autoBackgrounds}
              onChange={(e) => handleAutoToggleChange(e.target.checked)}
            />
            Sélection automatique au moment de la génération
          </label>
        </div>
        {autoBackgrounds ? (
          <div className="auto-bg-notice">
            <span className="auto-bg-notice__icon">🤖</span>
            <div>
              <strong>Sélection automatique activée</strong>
              <p>
                Les sons d'ambiance seront choisis automatiquement lors de la génération audio,
                en fonction du texte du scénario généré. Vous pouvez parcourir la bibliothèque
                ci-dessous pour vous faire une idée des sons disponibles.
              </p>
            </div>
          </div>
        ) : (
          <div className="ambient-none-option">
            <label>
              <input
                type="radio"
                name="ambient-choice"
                checked={!selectedAmbient}
                onChange={() => handleAmbientSelect(null)}
              />
              Aucun fond continu
            </label>
          </div>
        )}
        <div className="background-library">
          {backgroundSounds?.map((sound) => {
            const isAmbient = selectedAmbient === sound.path;
            const isPunctual = selectedPunctual.includes(sound.path);
            const isSelected = isAmbient || isPunctual;
            return (
              <div
                key={sound.path}
                className={`background-item${isSelected ? " background-item--selected" : ""}`}
              >
                <div className="background-header">
                  <strong className="background-item__title">{sound.name}</strong>
                  {sound.category && (
                    <span className="background-item__category">{sound.category}</span>
                  )}
                  {sound.duration != null && (
                    <span className="background-item__duration">
                      {formatDuration(sound.duration)}
                    </span>
                  )}
                  <audio controls src={sound.preview} />
                </div>
                {sound.description && (
                  <p className="background-item__description">{sound.description}</p>
                )}
                {sound.tags && sound.tags.length > 0 && (
                  <div className="background-item__tags">
                    {sound.tags.map((tag) => (
                      <span key={tag} className="background-tag">{tag}</span>
                    ))}
                  </div>
                )}
                {!autoBackgrounds && (
                  <div className="background-selectors">
                    <label>
                      <input
                        type="radio"
                        name="ambient-choice"
                        checked={isAmbient}
                        onChange={() => handleAmbientSelect(sound.path)}
                      />
                      Fond continu
                    </label>
                    <label>
                      <input
                        type="checkbox"
                        checked={isPunctual}
                        onChange={() => handlePunctualToggle(sound.path)}
                      />
                      Son ponctuel
                    </label>
                  </div>
                )}
              </div>
            );
          })}
          {!backgroundSounds?.length && <p>Aucun son trouvé. Ajoutez-en via l'upload ci-dessus.</p>}
        </div>
      </section>

      {ttsProvider === "elevenlabs" && (
        <section className="card voice-selection-card">
          <div className="voice-selection-header">
            <div>
              <h3>Choisir une voix ElevenLabs</h3>
              <p>Écoutez un extrait de chaque voix et touchez la carte pour la sélectionner.</p>
            </div>
          </div>
          <div className="voice-grid">
            {ELEVEN_LABS_VOICE_OPTIONS.map((voice, index) => {
              const isSelected = selectedVoiceId === voice.id;
              return (
                <div
                  key={voice.id}
                  className={`voice-card${isSelected ? " selected" : ""}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleVoiceCardSelect(voice.id)}
                  onKeyDown={(event) => handleVoiceCardKeyDown(voice.id, event)}
                >
                  <input
                    type="radio"
                    name="voice-choice"
                    checked={isSelected}
                    readOnly
                    className="sr-only"
                  />
                  <div className="voice-card-header">
                    <span className="voice-pill">Voix {index + 1}</span>
                    <span
                      className={`voice-select-indicator${isSelected ? " active" : ""}`}
                      aria-hidden="true"
                    />
                  </div>
                  <div className="voice-card-actions">
                    <button
                      type="button"
                      className="voice-preview-button"
                      onClick={(event) => {
                        event.stopPropagation();
                        handlePreviewVoice(voice.id);
                      }}
                      disabled={Boolean(voicePreviewLoading[voice.id])}
                      aria-label={`Écouter la voix ${index + 1}`}
                    >
                      {voicePreviewLoading[voice.id] ? "…" : "▶"}
                    </button>
                    {voicePreviewErrors[voice.id] && <p className="error tiny">{voicePreviewErrors[voice.id]}</p>}
                    {voicePreviewUrls[voice.id] && (
                      <audio
                        controls
                        src={voicePreviewUrls[voice.id]}
                        preload="none"
                        onClick={(event) => event.stopPropagation()}
                      />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {nextStatus && <p>{nextStatus}</p>}
      <button className="link" onClick={goNext} disabled={!sessionId}>
        Étape suivante
      </button>
    </div>
  );
}
