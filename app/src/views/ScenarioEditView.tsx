import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  advanceStep,
  fetchSelectedScenario,
  selectScenario,
  fetchScenarioAudio,
  synthesizeScenarioAudio,
  getScenarioAudioUrl
} from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

type ScenarioPartDraft = { titre: string; texte_narration: string };

export function ScenarioEditView() {
  const { sessionId, setCurrentStep, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [partsDraft, setPartsDraft] = useState<ScenarioPartDraft[]>([]);
  const [freeText, setFreeText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [audioStatus, setAudioStatus] = useState<string | null>(null);

  const selectionQuery = useQuery({
    queryKey: ["selected-scenario", sessionId],
    queryFn: () => fetchSelectedScenario(sessionId!),
    enabled: Boolean(sessionId)
  });

  const audioQuery = useQuery({
    queryKey: ["scenario-audio", sessionId],
    queryFn: () => fetchScenarioAudio(sessionId!),
    enabled: Boolean(sessionId)
  });

  useEffect(() => {
    if (!selectionQuery.data) return;
    const payload = extractScenario(selectionQuery.data);
    setTitle(payload.titre ?? "");
    if (Array.isArray(payload.parties) && payload.parties.length > 0) {
      setPartsDraft(
        payload.parties.map((part: any, idx: number) => ({
          titre: part?.titre ?? `Partie ${idx + 1}`,
          texte_narration: part?.texte_narration ?? part?.texte ?? ""
        }))
      );
      setFreeText("");
    } else {
      setPartsDraft([]);
      setFreeText(payload.texte_narration ?? payload.texte ?? "");
    }
  }, [selectionQuery.data]);

  const audioSrc = useMemo(() => {
    if (!sessionId || !audioQuery.data?.path) return null;
    const base = getScenarioAudioUrl(sessionId).replace(/\/$/, "");
    const cacheBust = audioQuery.data.generated_at ? `?ts=${encodeURIComponent(audioQuery.data.generated_at)}` : "";
    return `${base}${cacheBust}`;
  }, [audioQuery.data, sessionId]);

  if (!sessionId) return <p>Démarrez une session.</p>;
  if (selectionQuery.isLoading) return <p>Chargement du scénario sélectionné...</p>;
  if (!selectionQuery.data) return <p>Aucun scénario sélectionné. Retournez à l'étape précédente.</p>;

  const persistScenario = async () => {
    if (!sessionId || !selectionQuery.data) return;
    const updated = buildUpdatedScenario(selectionQuery.data, title, partsDraft, freeText);
    await selectScenario(sessionId, updated);
    await queryClient.invalidateQueries({ queryKey: ["selected-scenario", sessionId] });
  };

  const handleSubmit = async (evt: FormEvent) => {
    evt.preventDefault();
    setStatus("Sauvegarde de vos modifications...");
    await persistScenario();
    await advanceStep(sessionId, "scenario_edit", { titre: title });
    updateProgress({ scenarioEdited: true });
    setCurrentStep("final_validation");
    navigate("/step/final_validation");
  };

  const saveDraft = async () => {
    setStatus("Scénario en cours d'enregistrement...");
    await persistScenario();
    setStatus("Scénario mis à jour.");
  };

  const regenerateAudio = async () => {
    if (!sessionId) return;
    setAudioStatus("Génération d'un nouvel audio...");
    await persistScenario();
    await synthesizeScenarioAudio(sessionId);
    await audioQuery.refetch();
    setAudioStatus("Audio régénéré.");
  };

  const addPart = () => {
    setPartsDraft((prev) => [...prev, { titre: `Partie ${prev.length + 1}`, texte_narration: "" }]);
    setFreeText("");
  };

  const removePart = (index: number) => {
    setPartsDraft((prev) => prev.filter((_, idx) => idx !== index));
  };

  return (
    <div className="step-view">
      <h2>Modifier le scénario</h2>
      <form onSubmit={handleSubmit} className="form-grid">
        <label>
          Titre du scénario
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>

        <section className="card">
          <h3>Structure narrative</h3>
          {partsDraft.length === 0 ? (
            <>
              <label>
                Corps du scénario
                <textarea rows={10} value={freeText} onChange={(e) => setFreeText(e.target.value)} />
              </label>
              <button type="button" className="link" onClick={addPart}>
                Découper en parties
              </button>
            </>
          ) : (
            <>
              {partsDraft.map((part, idx) => (
                <div className="card" key={idx}>
                  <label>
                    Titre de la partie {idx + 1}
                    <input
                      value={part.titre}
                      onChange={(e) =>
                        setPartsDraft((prev) =>
                          prev.map((p, i) => (i === idx ? { ...p, titre: e.target.value } : p))
                        )
                      }
                    />
                  </label>
                  <label>
                    Contenu
                    <textarea
                      rows={6}
                      value={part.texte_narration}
                      onChange={(e) =>
                        setPartsDraft((prev) =>
                          prev.map((p, i) => (i === idx ? { ...p, texte_narration: e.target.value } : p))
                        )
                      }
                    />
                  </label>
                  <button type="button" className="link" onClick={() => removePart(idx)}>
                    Supprimer cette partie
                  </button>
                </div>
              ))}
              <button type="button" className="link" onClick={addPart}>
                Ajouter une partie
              </button>
            </>
          )}
        </section>

        <section className="card">
          <h3>Pré-écoute audio</h3>
          {audioQuery.isFetching && <p>Chargement de l'audio...</p>}
          {audioSrc && (
            <>
              <audio controls src={audioSrc} preload="auto" />
              {audioQuery.data?.generated_at && (
                <p>Dernière génération : {new Date(audioQuery.data.generated_at).toLocaleString()}</p>
              )}
            </>
          )}
          {!audioSrc && !audioQuery.isFetching && <p>Aucun audio disponible pour l'instant.</p>}
          <button type="button" onClick={regenerateAudio}>
            Sauvegarder & régénérer l'audio
          </button>
          {audioStatus && <p>{audioStatus}</p>}
        </section>

        <div className="card">
          <button type="button" onClick={saveDraft}>
            Sauvegarder le texte
          </button>
          <button type="submit">Valider l'édition</button>
        </div>
      </form>
      {status && <p>{status}</p>}
    </div>
  );
}

function extractScenario(raw: Record<string, any>): Record<string, any> {
  if (raw?.scenario && typeof raw.scenario === "object") {
    return raw.scenario;
  }
  return raw;
}

function buildUpdatedScenario(
  original: Record<string, any>,
  title: string,
  parts: ScenarioPartDraft[],
  freeText: string
) {
  const base = { ...original };
  const target = base.scenario && typeof base.scenario === "object" ? { ...base.scenario } : { ...base };
  target.titre = title;
  if (parts.length > 0) {
    target.parties = parts.map((part, idx) => ({
      titre: part.titre || `Partie ${idx + 1}`,
      texte_narration: part.texte_narration ?? ""
    }));
    delete target.texte;
    delete target.texte_narration;
  } else {
    delete target.parties;
    target.texte_narration = freeText;
  }
  if (base.scenario && typeof base.scenario === "object") {
    return { ...base, scenario: target };
  }
  return target;
}
