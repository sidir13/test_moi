import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { advanceStep, fetchProjectProfile } from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

export function ProjectDetailsView() {
  const { sessionId, projectName, currentStep, setCurrentStep, setProgress } = useSessionStore();
  const navigate = useNavigate();
  const DEFAULT_DURATION_SECONDS = 120;
  const MIN_DURATION_SECONDS = 30;
  const [notes, setNotes] = useState("");
  const [audience, setAudience] = useState("");
  const [tone, setTone] = useState("");
  const [voiceInstructions, setVoiceInstructions] = useState("");
  const [targetDuration, setTargetDuration] = useState(DEFAULT_DURATION_SECONDS);
  const [ttsProvider, setTtsProvider] = useState<"qwen" | "elevenlabs">("elevenlabs");
  const [includeCitations, setIncludeCitations] = useState(true);
  const [sourceUsageLevel, setSourceUsageLevel] = useState<"leger" | "modere" | "central">("modere");
  const [status, setStatus] = useState<string | null>(null);
  const notesPrefilledFor = useRef<string | null>(null);
  const progressPrefilledFor = useRef<string | null>(null);
  const preferencesPrefilledFor = useRef<string | null>(null);

  const profileQuery = useQuery({
    queryKey: ["project-profile", projectName],
    queryFn: () => fetchProjectProfile(projectName!),
    enabled: Boolean(projectName)
  });

  if (!sessionId) {
    return <p>Créez ou sélectionnez un projet pour continuer.</p>;
  }

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
    const durationSettings = pref?.duration;
    const clampDuration = (value: number): number => {
      if (!durationSettings) return value;
      const min = durationSettings.min;
      const max = durationSettings.max;
      return Math.min(max, Math.max(min, value));
    };
    setAudience(profileQuery.data.audience ?? "");
    setTone(profileQuery.data.tone ?? "");
    setVoiceInstructions(profileQuery.data.voice_instructions ?? "");
    const providerValue = profileQuery.data.tts_provider === "qwen" ? "qwen" : "elevenlabs";
    setTtsProvider(providerValue);
    setIncludeCitations(profileQuery.data.include_citations !== false);
    const savedSourceLevel = profileQuery.data.source_usage_level;
    if (savedSourceLevel === "leger" || savedSourceLevel === "modere" || savedSourceLevel === "central") {
      setSourceUsageLevel(savedSourceLevel);
    }
    const fallbackDuration =
      profileQuery.data.target_duration ??
      durationSettings?.default ??
      DEFAULT_DURATION_SECONDS;
    const normalizedDuration =
      typeof fallbackDuration === "number" ? fallbackDuration : DEFAULT_DURATION_SECONDS;
    setTargetDuration(clampDuration(normalizedDuration || DEFAULT_DURATION_SECONDS));
    preferencesPrefilledFor.current = projectName;
  }, [profileQuery.data, projectName]);

  useEffect(() => {
    if (!projectName || !profileQuery.data) return;
    if (progressPrefilledFor.current === projectName) return;
    const hasStoredScenarios = Boolean(profileQuery.data.last_scenarios?.length);
    const hasFinalScenario = Boolean(profileQuery.data.final_scenario);
    const scenariosReady = hasStoredScenarios || hasFinalScenario;
    const scenarioChosen = hasFinalScenario;
    const audioReady = Boolean(profileQuery.data.final_audio?.path || profileQuery.data.audio_selection?.voices?.length);
    const legacyTranscriptionsReviewed =
      Boolean(profileQuery.data.final_audio?.path) || hasStoredScenarios || hasFinalScenario;
    setProgress({
      audioReady,
      transcriptionsReviewed: legacyTranscriptionsReviewed,
      scenariosReady,
      scenarioChosen,
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
  const formattedDuration = useMemo(() => {
    const mins = Math.floor(targetDuration / 60);
    const secs = targetDuration % 60;
    const minutesLabel = mins > 0 ? `${mins} min` : "";
    const secondsLabel = `${secs.toString().padStart(2, "0")} s`;
    return [minutesLabel, secondsLabel].filter(Boolean).join(" ");
  }, [targetDuration]);
  const sliderRangeLabel = useMemo(() => {
    const formatBound = (value: number) => {
      if (value % 60 === 0) {
        return `${value / 60} min`;
      }
      return `${value}s`;
    };
    return `${formatBound(durationSettings.min)} et ${formatBound(durationSettings.max)}`;
  }, [durationSettings]);

  const formatOptionLabel = (value: string) =>
    value
      .split("_")
      .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
      .join(" ");

  const isElevenLabsProvider = ttsProvider === "elevenlabs";
  const toggleProvider = () => {
    setTtsProvider((prev) => (prev === "elevenlabs" ? "qwen" : "elevenlabs"));
  };
  const handleSubmit = async (evt: FormEvent) => {
    evt.preventDefault();
    setStatus("Envoi en cours...");
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
    setStatus("Notes enregistrées");
    setTimeout(() => setStatus(null), 2000);
    setCurrentStep("audio_sources");
    navigate("/step/audio_sources");
  };

  return (
    <div className="step-view">
      <h2>Détails du projet</h2>
      <p>Précisez le contexte, le public, le ton et les consignes vocales pour guider les scénarios. Étape actuelle: {currentStep}</p>
      {profileQuery.isFetching && <p>Chargement des notes enregistrées…</p>}
      <form onSubmit={handleSubmit} className="form-grid">
        <label className="field-block">
          <span>Contexte du scénario</span>
          <textarea
            rows={6}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Quelle histoire souhaitez-vous raconter ?"
          />
        </label>

        <div className="preference-grid">
          <label className="field-block">
            <span>Public cible (optionnel)</span>
            <select value={audience} onChange={(e) => setAudience(e.target.value)}>
              <option value="">Sélectionner</option>
              {audienceOptions.map((option) => (
                <option key={option} value={option}>
                  {formatOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>
          <label className="field-block">
            <span>Ton narratif (optionnel)</span>
            <select value={tone} onChange={(e) => setTone(e.target.value)}>
              <option value="">Sélectionner</option>
              {toneOptions.map((option) => (
                <option key={option} value={option}>
                  {formatOptionLabel(option)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="field-block">
          <span>Consignes vocales (optionnel)</span>
          <textarea
            rows={4}
            value={voiceInstructions}
            onChange={(e) => setVoiceInstructions(e.target.value)}
            placeholder="Ex: Use a female narrator, warm and composed..."
          />
        </label>
        <label className="field-block">
          <span>Moteur de synthèse vocale</span>
          <div className="provider-switch">
            <span className={`provider-label ${!isElevenLabsProvider ? "active" : ""}`}>Qwen local</span>
            <button
              type="button"
              className={`switch-toggle ${isElevenLabsProvider ? "on" : ""}`}
              onClick={toggleProvider}
              aria-pressed={isElevenLabsProvider}
              aria-label="Basculer entre Qwen local et ElevenLabs"
            >
              <span className="thumb" />
            </button>
            <span className={`provider-label ${isElevenLabsProvider ? "active" : ""}`}>ElevenLabs</span>
          </div>
          <p className="field-hint">
            {isElevenLabsProvider
              ? "Voix ElevenLabs hébergées (qualité et expressivité maximales)."
              : "Synthèse locale Qwen : aucune dépendance cloud, voix générée d'après vos consignes."}
          </p>
        </label>

        <div className="preference-grid">
          <label className="field-block">
            <span>Utilisation des sources audio</span>
            <select value={sourceUsageLevel} onChange={(e) => setSourceUsageLevel(e.target.value as "leger" | "modere" | "central")}>
              <option value="leger">Léger — contexte uniquement</option>
              <option value="modere">Modéré — sourcing équilibré</option>
              <option value="central">Central — élément narratif majeur</option>
            </select>
            <small>Détermine l'importance des transcriptions dans le récit.</small>
          </label>
          <label className="field-block" style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: "0.5rem" }}>
            <input
              type="checkbox"
              checked={includeCitations}
              onChange={(e) => setIncludeCitations(e.target.checked)}
            />
            <span>Inclure les citations directes des sources</span>
          </label>
        </div>

        <label className="field-block slider-field">
          <div className="slider-header">
            <span>Durée audio ciblée</span>
            <strong>{formattedDuration}</strong>
          </div>
          <input
            type="range"
            min={durationSettings.min}
            max={durationSettings.max}
            step={durationSettings.step}
            value={targetDuration}
            onChange={(e) => setTargetDuration(Number(e.target.value))}
          />
          <small>Entre {sliderRangeLabel}</small>
        </label>

        <button type="submit">Sauvegarder & continuer</button>
      </form>
      {status && <p>{status}</p>}
    </div>
  );
}
