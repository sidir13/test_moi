import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { advanceStep, fetchProjectProfile } from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

export function ProjectDetailsView() {
  const { sessionId, projectName, currentStep, setCurrentStep, setProgress } = useSessionStore();
  const navigate = useNavigate();
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const notesPrefilledFor = useRef<string | null>(null);
  const progressPrefilledFor = useRef<string | null>(null);

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
    if (progressPrefilledFor.current === projectName) return;
    const hasStoredScenarios = Boolean(profileQuery.data.last_scenarios?.length);
    const hasFinalScenario = Boolean(profileQuery.data.final_scenario);
    const scenariosReady = hasStoredScenarios || hasFinalScenario;
    const scenarioChosen = hasFinalScenario;
    const audioReady = Boolean(profileQuery.data.final_audio?.path || profileQuery.data.audio_selection?.voices?.length);
    setProgress({
      audioReady,
      scenariosReady,
      scenarioChosen,
      scenarioEdited: false
    });
    progressPrefilledFor.current = projectName;
  }, [profileQuery.data, projectName, setProgress]);

  const handleSubmit = async (evt: FormEvent) => {
    evt.preventDefault();
    setStatus("Envoi en cours...");
    await advanceStep(sessionId, "project_details", { notes });
    setStatus("Notes enregistrées");
    setTimeout(() => setStatus(null), 2000);
    setCurrentStep("audio_sources");
    navigate("/step/audio_sources");
  };

  return (
    <div className="step-view">
      <h2>Détails du projet</h2>
      <p>Ajoutez un brief pour guider les scénarios. Étape actuelle: {currentStep}</p>
      {profileQuery.isFetching && <p>Chargement des notes enregistrées…</p>}
      <form onSubmit={handleSubmit} className="form-grid">
        <textarea
          rows={6}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Quelle histoire souhaitez-vous raconter ?"
        />
        <button type="submit">Sauvegarder & continuer</button>
      </form>
      {status && <p>{status}</p>}
    </div>
  );
}
