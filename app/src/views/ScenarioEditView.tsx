import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { advanceStep, fetchSelectedScenario, selectScenario } from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

export function ScenarioEditView() {
  const { sessionId, setCurrentStep, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [partsDraft, setPartsDraft] = useState<Array<{ titre?: string; texte_narration?: string }>>([]);
  const [status, setStatus] = useState<string | null>(null);

  const selectionQuery = useQuery({
    queryKey: ["selected-scenario", sessionId],
    queryFn: () => fetchSelectedScenario(sessionId!),
    enabled: Boolean(sessionId)
  });

  useEffect(() => {
    if (selectionQuery.data) {
      setTitle((selectionQuery.data as any).titre ?? "");
      setPartsDraft((selectionQuery.data as any).parties ?? []);
    }
  }, [selectionQuery.data]);

  if (!sessionId) return <p>Démarrez une session.</p>;
  if (selectionQuery.isLoading) return <p>Chargement du scénario sélectionné...</p>;
  if (!selectionQuery.data) return <p>Aucun scénario sélectionné. Retournez à l'étape précédente.</p>;

  const handleSubmit = async (evt: FormEvent) => {
    evt.preventDefault();
    setStatus("Sauvegarde...");
    const updatedScenario = {
      ...selectionQuery.data,
      titre: title,
      parties: partsDraft
    };
    await selectScenario(sessionId, updatedScenario);
    await advanceStep(sessionId, "scenario_edit", { titre: title });
    updateProgress({ scenarioEdited: true });
    setCurrentStep("final_validation");
    navigate("/step/final_validation");
  };

  return (
    <div className="step-view">
      <h2>Modifier le scénario</h2>
      <form onSubmit={handleSubmit} className="form-grid">
        <label>
          Titre du scénario
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        {partsDraft.map((part, idx) => (
          <label key={idx}>
            {part.titre || `Partie ${idx + 1}`}
            <textarea
              rows={6}
              value={part.texte_narration ?? ""}
              onChange={(e) =>
                setPartsDraft((prev) =>
                  prev.map((p, i) => (i === idx ? { ...p, texte_narration: e.target.value } : p))
                )
              }
            />
          </label>
        ))}
        <button type="submit">Valider l'édition</button>
      </form>
      {status && <p>{status}</p>}
    </div>
  );
}
