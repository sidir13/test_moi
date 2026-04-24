import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  advanceStep,
  fetchProjectTranscriptions,
  fetchProjectKnowledgeGraph,
  updateProjectTranscription,
  ProjectTranscription
} from "../api/client";
import { API_BASE_URL } from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

type SavePayload = {
  fileName: string;
  text: string;
};

export function TranscriptionReviewView() {
  const { projectName, sessionId, setCurrentStep, updateProgress } = useSessionStore();
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const dirtyRef = useRef<Record<string, boolean>>({});
  const [saveFeedback, setSaveFeedback] = useState<Record<string, string | null>>({});
  const [globalStatus, setGlobalStatus] = useState<string | null>(null);
  const transcriptionsQuery = useQuery({
    queryKey: ["project-transcriptions", projectName],
    queryFn: () => fetchProjectTranscriptions(projectName!),
    enabled: Boolean(projectName)
  });

  const graphQuery = useQuery({
    queryKey: ["project-knowledge-graph", projectName],
    queryFn: () => fetchProjectKnowledgeGraph(projectName!),
    enabled: Boolean(projectName)
  });

  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);

  useEffect(() => {
    const entries = transcriptionsQuery.data;
    if (!entries) return;
    setDrafts((prev) => {
      const next: Record<string, string> = {};
      entries.forEach((entry) => {
        if (dirtyRef.current[entry.file_name] && prev[entry.file_name] !== undefined) {
          next[entry.file_name] = prev[entry.file_name];
        } else {
          next[entry.file_name] = entry.transcription;
        }
      });
      return next;
    });
    setDirty((current) => {
      const filtered: Record<string, boolean> = {};
      entries.forEach((entry) => {
        filtered[entry.file_name] = current[entry.file_name] ?? false;
      });
      dirtyRef.current = filtered;
      return filtered;
    });
  }, [transcriptionsQuery.data]);

  const saveMutation = useMutation({
    mutationFn: ({ fileName, text }: SavePayload) =>
      updateProjectTranscription(projectName!, { file_name: fileName, transcription: text }),
    onSuccess: (data) => {
      setDirty((prev) => ({ ...prev, [data.file_name]: false }));
      setDrafts((prev) => ({ ...prev, [data.file_name]: data.transcription }));
      setSaveFeedback((prev) => ({ ...prev, [data.file_name]: "Transcription enregistrée." }));
      transcriptionsQuery.refetch();
    },
    onError: (err, variables) => {
      const message = err instanceof Error ? err.message : "Impossible d'enregistrer la transcription.";
      if (variables?.fileName) {
        setSaveFeedback((prev) => ({ ...prev, [variables.fileName]: message }));
      }
    }
  });

  const transcriptions = useMemo<ProjectTranscription[]>(() => transcriptionsQuery.data ?? [], [transcriptionsQuery.data]);

  if (!projectName || !sessionId) {
    return <p>Sélectionnez un projet et une session pour réviser vos transcriptions.</p>;
  }

  const handleChange = (fileName: string, value: string) => {
    setDrafts((prev) => ({ ...prev, [fileName]: value }));
    setDirty((prev) => ({ ...prev, [fileName]: true }));
    setSaveFeedback((prev) => ({ ...prev, [fileName]: null }));
  };

  const handleSave = (fileName: string) => {
    const text = drafts[fileName] ?? "";
    saveMutation.mutate({ fileName, text });
  };

  const handleExport = (fileName: string) => {
    const text = drafts[fileName] ?? "";
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${fileName}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleContinue = async (evt: FormEvent) => {
    evt.preventDefault();
    if (!sessionId) return;
    setGlobalStatus("Enregistrement de la validation…");
    try {
      await advanceStep(sessionId, "transcription_review", {
        files: transcriptions.map((t) => t.file_name)
      });
      updateProgress({ transcriptionsReviewed: true });
      setCurrentStep("scenario_review");
      navigate("/step/scenario_review");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Impossible de continuer.";
      setGlobalStatus(message);
      return;
    }
    setGlobalStatus(null);
  };

  return (
    <div className="step-view">
      <h2>Réviser et corriger les transcriptions</h2>
      <p>
        Vérifiez les transcriptions automatiques, corrigez les erreurs éventuelles et exportez un fichier texte si besoin.
        Toute modification provoque une mise à jour du résumé après enregistrement.
      </p>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
        <button type="button" onClick={() => transcriptionsQuery.refetch()} disabled={transcriptionsQuery.isFetching}>
          {transcriptionsQuery.isFetching ? "Actualisation…" : "Actualiser les transcriptions"}
        </button>
        {globalStatus && <span>{globalStatus}</span>}
      </div>
      {transcriptionsQuery.isLoading && <p>Chargement des transcriptions…</p>}
      {!transcriptionsQuery.isLoading && transcriptions.length === 0 && (
        <div className="card">
          <p>
            Aucune transcription disponible pour le moment. Vérifiez que vos pistes vocales ont bien été analysées ou réessayez
            plus tard.
          </p>
        </div>
      )}

      {transcriptions.map((entry) => {
        const summary = entry.summary;
        const currentText = drafts[entry.file_name] ?? entry.transcription;
        const isDirty = dirty[entry.file_name];
        return (
          <section className="card" key={entry.file_name} style={{ marginBottom: "1rem" }}>
            <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
              <div>
                <h3 style={{ margin: 0 }}>{entry.file_name}</h3>
                <small>{entry.source}</small>
              </div>
              {isDirty && <span className="badge warning">Modifications non sauvegardées</span>}
            </header>
            {summary && (
              <details style={{ marginTop: "0.5rem" }}>
                <summary>Résumé automatique</summary>
                {summary.global_summary && <p>{summary.global_summary}</p>}
                {summary.topics && summary.topics.length > 0 && (
                  <ul>
                    {summary.topics.map((topic, idx) => (
                      <li key={`${entry.file_name}-topic-${idx}`}>
                        <strong>{topic.title} :</strong> {topic.summary}
                        {topic.keywords && topic.keywords.length > 0 && (
                          <small> — Mots-clés : {topic.keywords.join(", ")}</small>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </details>
            )}
            <label className="field-block" style={{ marginTop: "0.75rem" }}>
              <span>Texte de la transcription</span>
              <textarea
                rows={8}
                value={currentText}
                onChange={(e) => handleChange(entry.file_name, e.target.value)}
              />
            </label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "0.5rem" }}>
              <button type="button" onClick={() => handleSave(entry.file_name)} disabled={saveMutation.isPending}>
                Enregistrer
              </button>
              <button type="button" onClick={() => handleExport(entry.file_name)}>
                Exporter (.txt)
              </button>
              {saveFeedback[entry.file_name] && <span>{saveFeedback[entry.file_name]}</span>}
            </div>
          </section>
        );
      })}

      {graphQuery.data && graphQuery.data.events.length > 0 && (
        <section className="card" style={{ marginBottom: "1rem" }}>
          <h3>Événements identifiés</h3>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
            <thead>
              <tr>
                {["Période", "Événement", "Acteurs", "Lieux"].map((h) => (
                  <th key={h} style={{ textAlign: "left", padding: "0.4rem 0.6rem", borderBottom: "1px solid #ccc" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {graphQuery.data.events.map((ev, idx) => (
                <tr key={idx} style={{ borderBottom: "1px solid #eee" }}>
                  <td style={{ padding: "0.4rem 0.6rem", whiteSpace: "nowrap" }}>{ev.approximate_time ?? "—"}</td>
                  <td style={{ padding: "0.4rem 0.6rem" }}>
                    <strong>{ev.title}</strong>
                    {ev.description && <><br /><small style={{ color: "#666" }}>{ev.description}</small></>}
                  </td>
                  <td style={{ padding: "0.4rem 0.6rem" }}>{ev.actors?.join(", ") ?? "—"}</td>
                  <td style={{ padding: "0.4rem 0.6rem" }}>{ev.places?.join(", ") ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {graphQuery.data && graphQuery.data.graph.nodes.length > 0 && (
        <section className="card" style={{ marginBottom: "1rem" }}>
          <h3>Graphe de connaissances</h3>
          <iframe
            src={`${API_BASE_URL}/projects/${encodeURIComponent(projectName!)}/knowledge-graph-view`}
            style={{ width: "100%", height: "600px", border: "none", borderRadius: "4px" }}
            title="Graphe de connaissances"
          />
        </section>
      )}

      <form onSubmit={handleContinue} className="card">
        <button type="submit" disabled={transcriptions.length === 0 || saveMutation.isPending}>
          Continuer vers les scénarios
        </button>
        {transcriptions.length === 0 && <p>Attendez qu'au moins une transcription soit disponible pour continuer.</p>}
      </form>
    </div>
  );
}
