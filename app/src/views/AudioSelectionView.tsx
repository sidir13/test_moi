import { DragEvent, FormEvent, useEffect, useRef, useState } from "react";
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
  fetchProjectProfile
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
  const [selectedBackgrounds, setSelectedBackgrounds] = useState<string[]>([]);
  const [selectedVoices, setSelectedVoices] = useState<string[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string | null>(null);
  const [backgroundTitle, setBackgroundTitle] = useState("");
  const [backgroundFile, setBackgroundFile] = useState<File | null>(null);
  const [backgroundStatus, setBackgroundStatus] = useState<string | null>(null);
  const [nextStatus, setNextStatus] = useState<string | null>(null);
  const hiddenBackgroundInput = useRef<HTMLInputElement | null>(null);
  const voicesRef = useRef<string[]>([]);
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
  const ttsProvider = profileQuery.data?.tts_provider === "elevenlabs" ? "elevenlabs" : "qwen";
  const saveSelection = useMutation({
    mutationFn: (payload: { voices: string[]; backgrounds: string[]; tts_voice_id?: string | null }) =>
      saveAudioSelection(sessionId!, { project_name: projectName!, ...payload }),
    onSuccess: (data) => {
      selectionQuery.refetch();
      if (data.voices.length > 0) {
        updateProgress({ audioReady: true });
      }
    }
  });
  const persistSelection = (voices: string[], backgrounds: string[], voiceId?: string | null) => {
    const payload: { voices: string[]; backgrounds: string[]; tts_voice_id?: string | null } = { voices, backgrounds };
    if (voiceId) {
      payload.tts_voice_id = voiceId;
    }
    saveSelection.mutate(payload);
  };

  if (!sessionId || !projectName) {
    return <p>Sélectionnez d'abord un projet.</p>;
  }

  useEffect(() => {
    if (selectionQuery.data) {
      setSelectedBackgrounds(selectionQuery.data.backgrounds || []);
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
    persistSelection(selectedVoices, selectedBackgrounds, normalized);
  };

  const updateSelection = (voices: string[], backgrounds: string[]) => {
    persistSelection(voices, backgrounds, selectedVoiceId);
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
        backgrounds: selectedBackgrounds,
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

  const toggleBackground = (sound: BackgroundSound) => {
    setSelectionError(null);
    setSelectedBackgrounds((prev) => {
      let next = prev;
      if (prev.includes(sound.path)) {
        next = prev.filter((p) => p !== sound.path);
      } else {
        if (prev.length >= 2) {
          setSelectionError("Vous pouvez choisir au maximum deux ambiances simultanées.");
          next = prev;
        } else {
          next = [...prev, sound.path];
        }
      }
      if (next !== prev) setSelectionError(null);
      updateSelection(selectedVoices, next);
      return next;
    });
  };

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
      updateSelection(next, selectedBackgrounds);
      updateProgress({ transcriptionsReviewed: false });
      return next;
    });
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
        <p>Pré-écoutez et choisissez jusqu'à deux sons pour enrichir la scénarisation.</p>
        {selectionError && <p className="error">{selectionError}</p>}
        <div className="background-library">
          {backgroundSounds?.map((sound) => (
            <div key={sound.path} className="background-item">
              <label>
                <input
                  type="checkbox"
                  checked={selectedBackgrounds.includes(sound.path)}
                  onChange={() => toggleBackground(sound)}
                />
                {sound.name}
              </label>
              <audio controls src={sound.preview} />
            </div>
          ))}
          {!backgroundSounds?.length && <p>Aucun son trouvé. Ajoutez-en via l'upload ci-dessus.</p>}
        </div>
      </section>

      {ttsProvider === "elevenlabs" && (
        <section className="card">
          <h3>Choisir une voix ElevenLabs</h3>
          <p>Ces voix sont codées en dur pour l’instant. Sélectionnez celle qui correspond le mieux à votre narration.</p>
          <label className="field-block">
            <span>Voix disponible</span>
            <select
              value={selectedVoiceId ?? ""}
              onChange={(e) => handleVoiceIdChange(e.target.value)}
            >
              <option value="">Sélectionner une voix</option>
              {ELEVEN_LABS_VOICE_OPTIONS.map((voice) => (
                <option key={voice.id} value={voice.id}>
                  {voice.label}
                </option>
              ))}
            </select>
          </label>
        </section>
      )}

      {nextStatus && <p>{nextStatus}</p>}
      <button className="link" onClick={goNext} disabled={!sessionId}>
        Étape suivante
      </button>
    </div>
  );
}
