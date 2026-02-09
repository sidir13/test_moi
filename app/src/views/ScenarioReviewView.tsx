import { FormEvent, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  advanceStep,
  generateScenarios,
  fetchScenarios,
  selectScenario,
  fetchSelectedScenario,
  fetchScenarioProgress,
  ScenarioProgressStep,
  synthesizeScenarioAudio
} from "../api/client";
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
  const scenarioProgressQuery = useQuery({
    queryKey: ["scenario-progress", sessionId],
    queryFn: () => fetchScenarioProgress(sessionId!),
    enabled: Boolean(sessionId),
    refetchInterval: isGenerating ? 1500 : false
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
    scenarioProgressQuery.refetch();
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
      .finally(() => {
        setIsGenerating(false);
        scenarioProgressQuery.refetch();
      });
  };

  const handleGenerate = async (evt: FormEvent) => {
    evt.preventDefault();
    setStatus("Génération en cours...");
    triggerGeneration();
  };

  const goNext = async () => {
    if (!sessionId) return;
    setStatus("Préparation de l'audio du scénario sélectionné…");
    try {
      await synthesizeScenarioAudio(sessionId);
    } catch (err) {
      console.error("Audio synthesis failed", err);
      setStatus("Audio non généré. Vérifiez vos instructions vocales.");
      return;
    }
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
      <ScenarioProgressDisplay steps={scenarioProgressQuery.data ?? []} isRunning={isGenerating} />
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
  const raw = scenario as any;
  const payload = raw?.scenario ?? raw;
  const title = payload?.titre ?? `Scénario ${index + 1}`;
  const axe = payload?.axe_narratif ?? "";
  const parties = Array.isArray(payload?.parties) ? payload.parties : [];
  const fallbackText =
    payload?.texte ??
    payload?.texte_narration ??
    (Array.isArray(parties) && parties.length === 0 && typeof payload === "object" ? JSON.stringify(payload, null, 2) : "");
  return (
    <article className={`scenario-card ${isSelected ? "selected" : ""}`}>
      <h4>{title}</h4>
      {axe && <p>Axe narratif : {axe}</p>}
      {parties.length > 0
        ? parties.map((part: any, idxPart: number) => (
            <div key={idxPart}>
              {part.titre && <strong>{part.titre}</strong>}
              {part.texte_narration && <p>{part.texte_narration}</p>}
            </div>
          ))
        : fallbackText && <pre>{fallbackText}</pre>}
      <button onClick={onSelect} className="link">
        {isSelected ? "Scénario sélectionné" : "Choisir ce scénario"}
      </button>
    </article>
  );
}

function isSameScenario(a?: Record<string, any>, b?: Record<string, any>) {
  if (!a || !b) return false;
  if ((a as any).scenario_index && (b as any).scenario_index) {
    return (a as any).scenario_index === (b as any).scenario_index;
  }
  const payloadA = (a as any).scenario ?? a;
  const payloadB = (b as any).scenario ?? b;
  if (payloadA?.id && payloadB?.id) return payloadA.id === payloadB.id;
  if (payloadA?.titre && payloadB?.titre) return payloadA.titre === payloadB.titre;
  return JSON.stringify(payloadA) === JSON.stringify(payloadB);
}

function ScenarioProgressDisplay({ steps, isRunning }: { steps: ScenarioProgressStep[]; isRunning: boolean }) {
  if (!steps || steps.length === 0) return null;
  const completed = steps.filter((step) => step.status === "done").length;
  const title = isRunning
    ? `Génération en cours (${completed}/${steps.length})`
    : `Dernière génération (${completed}/${steps.length} étapes achevées)`;

  const list = (
    <div className="progress-panel">
      <h3>{title}</h3>
      <ol className="progress-list">
        {steps.map((step, idx) => (
          <li key={idx} className={`progress-step status-${step.status ?? "pending"}`}>
            <div className="progress-header">
              <span>{step.label}</span>
              <span className="status-badge">{statusLabel(step.status)}</span>
            </div>
            {step.message && <p>{step.message}</p>}
          </li>
        ))}
      </ol>
    </div>
  );

  if (isRunning) {
    return (
      <div className="modal-backdrop">
        <div className="modal">{list}</div>
      </div>
    );
  }

  return <section className="card">{list}</section>;
}

function statusLabel(status?: string) {
  switch (status) {
    case "running":
      return "En cours";
    case "done":
      return "Terminé";
    case "error":
      return "Erreur";
    default:
      return "En attente";
  }
}
