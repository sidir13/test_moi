import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { advanceStep } from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

export function ProjectDetailsView() {
  const { sessionId, currentStep, setCurrentStep } = useSessionStore();
  const navigate = useNavigate();
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  if (!sessionId) {
    return <p>Créez ou sélectionnez un projet pour continuer.</p>;
  }

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
