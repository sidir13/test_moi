import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { advanceStep, generateScenarios, fetchScenarios, selectScenario, fetchSelectedScenario } from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

export function ScenarioReviewView() {
  const { sessionId, setCurrentStep, scenarioTarget, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("Souhaitez vous qu'on vous aide à choisir le meilleur scénario ?");
  const [status, setStatus] = useState<string | null>(null);
  const bootstrap = useRef(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const scenariosQuery = useQuery({
    queryKey: ["scenarios", sessionId],
    queryFn: () => fetchScenarios(sessionId!),
    enabled: Boolean(sessionId)
  });
  const selectedScenarioQuery = useQuery({
    queryKey: ["selected-scenario", sessionId],
    queryFn: () => fetchSelectedScenario(sessionId!),
    enabled: Boolean(sessionId)
  });

  if (!sessionId) {
    return <p>Session introuvable.</p>;
  }

  useEffect(() => {
    if (!sessionId || bootstrap.current) return;
    bootstrap.current = true;
    triggerGeneration();
  }, [prompt, scenarioTarget, sessionId, queryClient]);

  useEffect(() => {
    if (scenariosQuery.data && scenariosQuery.data.length > 0) {
      updateProgress({ scenariosReady: true });
    }
  }, [scenariosQuery.data, updateProgress]);

  useEffect(() => {
    if (selectedScenarioQuery.data) {
      updateProgress({ scenarioChosen: true });
    }
  }, [selectedScenarioQuery.data, updateProgress]);

  const triggerGeneration = () => {
    if (!sessionId) return;
    setIsGenerating(true);
    setStatus("Génération automatique des scénarios…");
    generateScenarios(sessionId, prompt, scenarioTarget)
      .then(() => {
        setStatus(`${scenarioTarget} scénarios ont été générés.`);
        queryClient.invalidateQueries({ queryKey: ["scenarios", sessionId] });
      })
      .catch((err) => {
        console.error("Auto scenario generation failed", err);
        setStatus("Impossible de générer automatiquement les scénarios.");
      })
      .finally(() => setIsGenerating(false));
  };

  const handleGenerate = async (evt: FormEvent) => {
    evt.preventDefault();
    setStatus("Génération en cours...");
    triggerGeneration();
  };

  const goNext = async () => {
    await advanceStep(sessionId, "scenario_review", { prompt });
    setCurrentStep("scenario_edit");
    navigate("/step/scenario_edit");
  };

  return (
    <div className="step-view">
      <h2>Consulter les scénarios générés</h2>
      <form onSubmit={handleGenerate} className="form-grid">
        <textarea rows={6} value={prompt} onChange={(e) => setPrompt(e.target.value)} />
        <button type="submit">Régénérer les scénarios</button>
      </form>
      {status && <p>{status}</p>}
      <section className="card">
        <h3>Scénarios disponibles</h3>
        {scenariosQuery.isLoading && <p>Chargement des scénarios...</p>}
        {scenariosQuery.data && scenariosQuery.data.length === 0 && <p>Aucun scénario pour le moment.</p>}
      {scenariosQuery.data &&
        scenariosQuery.data.map((scenario, idx) => (
          <ScenarioCard
            key={idx}
            scenario={scenario}
              index={idx}
              isSelected={isSameScenario(selectedScenarioQuery.data, scenario)}
              onSelect={async () => {
                await selectScenario(sessionId!, scenario);
                queryClient.invalidateQueries({ queryKey: ["selected-scenario", sessionId] });
                updateProgress({ scenarioChosen: true });
              }}
            />
          ))}
      </section>
      <button className="link" onClick={goNext} disabled={!selectedScenarioQuery.data}>
        Continuer vers l'édition
      </button>
      {isGenerating && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Génération des scénarios</h3>
            <p>Veuillez patienter pendant la génération (voir la console backend pour le détail des étapes).</p>
          </div>
        </div>
      )}
    </div>
  );
}

function ScenarioCard({
  scenario,
  index,
  isSelected,
  onSelect
}: {
  scenario: Record<string, any>;
  index: number;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const title = (scenario as any).titre ?? `Scénario ${index + 1}`;
  const axe = (scenario as any).axe_narratif ?? "";
  const parties = (scenario as any).parties ?? [];
  return (
    <article className={`scenario-card ${isSelected ? "selected" : ""}`}>
      <h4>{title}</h4>
      {axe && <p>Axe narratif : {axe}</p>}
      {parties.length > 0 &&
        parties.map((part: any, idxPart: number) => (
          <div key={idxPart}>
            <strong>{part.titre}</strong>
            <p>{part.texte_narration}</p>
          </div>
        ))}
      <button onClick={onSelect} className="link">
        {isSelected ? "Scénario sélectionné" : "Choisir ce scénario"}
      </button>
    </article>
  );
}

function isSameScenario(a?: Record<string, any>, b?: Record<string, any>) {
  if (!a || !b) return false;
  if (a.id && b.id) return a.id === b.id;
  if (a.titre && b.titre) return a.titre === b.titre;
  return JSON.stringify(a) === JSON.stringify(b);
}
