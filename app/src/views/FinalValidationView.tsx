import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { advanceStep } from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

export function FinalValidationView() {
  const { projectName, sessionId, setProjectName, setSessionId, setCurrentStep, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const [modalOpen, setModalOpen] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const confirm = async () => {
    if (!sessionId) return;
    setStatus("Sauvegarde en cours...");
    try {
      await advanceStep(sessionId, "final_validation", { confirmed: true });
      updateProgress({
        audioReady: false,
        scenariosReady: false,
        scenarioChosen: false,
        scenarioEdited: false
      });
      setSessionId(undefined);
      setProjectName(undefined);
      setCurrentStep("project_selection");
      setStatus("Projet finalisé et archivé. Retour aux projets.");
      setModalOpen(false);
      navigate("/");
    } catch (err) {
      setStatus((err as Error).message);
    }
  };

  return (
    <div className="step-view">
      <h2>Validation du scénario final</h2>
      <p>Projet sélectionné : {projectName ?? "aucun"}</p>
      <p>
        Cette étape confirme l'export audio et les métadonnées liées au projet. Vous pouvez revenir aux étapes
        précédentes pour ajuster les scénarios.
      </p>
      <div className="placeholder-card">
        <p>
          Audio et transcription enregistrés dans{" "}
          {projectName ? `data/projects/${projectName}/config.json` : "la configuration du projet"}.
        </p>
        <button onClick={() => setModalOpen(true)}>Confirmer la finalisation</button>
      </div>
      {status && <p>{status}</p>}
      {modalOpen && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Confirmer la validation</h3>
            <p>
              Voulez-vous archiver le projet <strong>{projectName}</strong> et verrouiller son scénario final ?
            </p>
            <div className="modal-actions">
              <button onClick={() => setModalOpen(false)}>Annuler</button>
              <button onClick={confirm}>Confirmer</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
