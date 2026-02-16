import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";

import {
  advanceStep,
  generateScenarios,
  fetchScenarios,
  selectScenario,
  fetchSelectedScenario,
  fetchScenarioProgress,
  fetchModels,
  ScenarioProgressStep,
  LlmModelInfo,
  synthesizeScenarioAudio
} from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

export function ScenarioReviewView() {
  const { sessionId, setCurrentStep, scenarioTarget, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const bootstrap = useRef(false);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isAdvancing, setIsAdvancing] = useState(false);
  const [advanceError, setAdvanceError] = useState<string | null>(null);
  const modelsQuery = useQuery({
    queryKey: ["models"],
    queryFn: fetchModels,
    staleTime: 1000 * 60 * 10,
  });
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

  const sortedScenarios = useMemo(() => {
    if (!scenariosQuery.data) {
      return [];
    }
    const clone = [...scenariosQuery.data];
    clone.sort((a, b) => {
      const rankA = getScenarioRank(a);
      const rankB = getScenarioRank(b);
      if (rankA !== null && rankB !== null && rankA !== rankB) {
        return rankA - rankB;
      }
      if (rankA !== null) return -1;
      if (rankB !== null) return 1;
      const idxA = (a as any).scenario_index ?? Number.MAX_SAFE_INTEGER;
      const idxB = (b as any).scenario_index ?? Number.MAX_SAFE_INTEGER;
      return idxA - idxB;
    });
    return clone;
  }, [scenariosQuery.data]);

  if (!sessionId) {
    return <p>Session introuvable.</p>;
  }

  useEffect(() => {
    if (!sessionId || bootstrap.current || (scenariosQuery.data && scenariosQuery.data.length > 0)) return;
    bootstrap.current = true;
    triggerGeneration();
  }, [sessionId, scenariosQuery.data]);

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
    const modelLabel = modelsQuery.data?.find((m) => m.id === selectedModel)?.label ?? "défaut";
    setStatus(`Génération des scénarios avec ${modelLabel}…`);
    generateScenarios(sessionId, prompt, scenarioTarget, "simple", selectedModel || undefined)
      .then(() => {
        setStatus(`${scenarioTarget} scénarios ont été générés (${modelLabel}).`);
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
    setAdvanceError(null);
    setIsAdvancing(true);
    setStatus("Préparation de l'audio du scénario sélectionné…");
    try {
      await synthesizeScenarioAudio(sessionId);
    } catch (err) {
      console.error("Audio synthesis failed", err);
      setAdvanceError(extractErrorMessage(err) ?? "Audio non généré. Vérifiez vos instructions vocales.");
      setStatus("Audio non généré. Vérifiez vos instructions vocales.");
      setIsAdvancing(false);
      return;
    }
    await advanceStep(sessionId, "scenario_review", { prompt });
    setCurrentStep("scenario_edit");
    navigate("/step/scenario_edit");
    setIsAdvancing(false);
  };

  return (
    <div className="step-view">
      <h2>Consulter les scénarios générés</h2>
      <form onSubmit={handleGenerate} className="form-grid">
        <textarea 
          rows={6} 
          value={prompt} 
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Souhaitez vous qu'on vous aide à choisir le meilleur scénario ?"
        />
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
          <label htmlFor="model-select" style={{ fontWeight: 500 }}>Modèle :</label>
          <select
            id="model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            style={{ flex: 1, minWidth: 180 }}
          >
            <option value="">Par défaut (Opus)</option>
            {modelsQuery.data?.map((m) => (
              <option key={m.id} value={m.id} title={m.description}>
                {m.label} — {m.provider}
              </option>
            ))}
          </select>
          <button type="submit" disabled={isGenerating}>
            {isGenerating ? "Génération…" : "Régénérer les scénarios"}
          </button>
        </div>
      </form>
      {status && <p>{status}</p>}
      <ScenarioProgressDisplay steps={scenarioProgressQuery.data ?? []} isRunning={isGenerating} />
      <section className="card">
        <h3>Scénarios disponibles</h3>
        {scenariosQuery.isLoading && <p>Chargement des scénarios...</p>}
        {scenariosQuery.data && sortedScenarios.length === 0 && <p>Aucun scénario pour le moment.</p>}
      {sortedScenarios.length > 0 &&
        sortedScenarios.map((scenario, idx) => {
          const displayIndex = getScenarioRank(scenario) ?? idx + 1;
          const cardKey =
            (scenario as any).scenario_index ??
            (scenario as any)?.scenario?.scenario_index ??
            `${idx}-${displayIndex}`;
          return (
            <ScenarioCard
              key={cardKey}
              scenario={scenario}
              displayIndex={displayIndex}
              isSelected={isSameScenario(selectedScenarioQuery.data, scenario)}
              onSelect={async () => {
                await selectScenario(sessionId!, scenario);
                queryClient.invalidateQueries({ queryKey: ["selected-scenario", sessionId] });
                updateProgress({ scenarioChosen: true });
              }}
            />
          );
        })}
      </section>
      {advanceError && <p className="alert error">{advanceError}</p>}
      <button className="link" onClick={goNext} disabled={!selectedScenarioQuery.data || isAdvancing}>
        Continuer vers l'édition
      </button>
      {isAdvancing && (
        <div className="modal-backdrop">
          <div className="modal">
            <h3>Préparation du scénario</h3>
            <p>Génération de l'audio en cours…</p>
          </div>
        </div>
      )}
    </div>
  );
}

function ScenarioCard({
  scenario,
  displayIndex,
  isSelected,
  onSelect
}: {
  scenario: Record<string, any>;
  displayIndex: number;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const raw = scenario as any;
  const payload = raw?.scenario ?? raw;
  const scenarioTitle =
    typeof payload?.titre === "string" && payload.titre.trim().length > 0 ? payload.titre.trim() : "";
  const heading = scenarioTitle ? `Scénario ${displayIndex} — ${scenarioTitle}` : `Scénario ${displayIndex}`;
  const axe = payload?.axe_narratif ?? "";
  const angle = payload?.angle_scenarisation ?? "";
  const ton = payload?.ton ?? "";
  const parties = Array.isArray(payload?.parties) ? payload.parties : [];
  const sources: string[] =
    payload?.metadata?.coherence_historique?.sources_citees ??
    [];
  const fallbackText =
    payload?.texte ??
    payload?.texte_narration ??
    (Array.isArray(parties) && parties.length === 0 && typeof payload === "object" ? JSON.stringify(payload, null, 2) : "");

  const angleLabels: Record<string, string> = {
    temoignage_croise: "Témoignages croisés (1ère personne)",
    chronique_sociale: "Chronique sociale (3ème personne)",
    journee_type: "Journée type",
    portrait_individuel: "Portrait individuel",
    avant_apres_evenement: "Avant / Après",
    mosaique_voix: "Mosaïque de voix",
    lettre_intime: "Lettre intime",
    recit_initiatique: "Récit initiatique",
  };

  return (
    <article className={`scenario-card ${isSelected ? "selected" : ""}`}>
      <h4>{heading}</h4>
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", fontSize: "0.85em", opacity: 0.85, marginBottom: "0.5rem" }}>
        {axe && <span title="Axe narratif">🎯 {axe}</span>}
        {angle && <span title="Angle de scénarisation">🎬 {angleLabels[angle] ?? angle}</span>}
        {ton && <span title="Ton">🎵 {ton}</span>}
      </div>
      {parties.length > 0
        ? parties.map((part: any, idxPart: number) => (
            <div key={idxPart}>
              {part.titre && <strong>{part.titre}</strong>}
              {part.texte_narration && <p>{part.texte_narration}</p>}
            </div>
          ))
        : fallbackText && <pre>{fallbackText}</pre>}
      {sources.length > 0 && (
        <details style={{ marginTop: "0.5rem", fontSize: "0.85em" }}>
          <summary>📚 Sources ({sources.length})</summary>
          <ul style={{ margin: "0.25rem 0", paddingLeft: "1.25rem" }}>
            {sources.map((src, i) => (
              <li key={i}>{src}</li>
            ))}
          </ul>
        </details>
      )}
      <button onClick={onSelect} className="link">
        {isSelected ? "Scénario sélectionné" : "Choisir ce scénario"}
      </button>
    </article>
  );
}

function getScenarioRank(raw?: Record<string, any>): number | null {
  if (!raw) return null;
  const immediate = parseRank((raw as any).quality_rank ?? (raw as any).rank);
  if (immediate !== null) return immediate;
  const payload = (raw as any).scenario ?? raw;
  return parseRank(payload?.quality_rank ?? payload?.rank);
}

function parseRank(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }
  return null;
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

function extractErrorMessage(err: unknown): string | null {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail.trim().length > 0) return detail;
    if (typeof err.message === "string" && err.message.trim().length > 0) return err.message;
  } else if (err instanceof Error) {
    return err.message;
  }
  return null;
}
