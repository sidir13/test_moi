import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import {
  createProject,
  createSession,
  fetchProjects,
  ProjectSummary,
  getProjectFinalAudioUrl
} from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

const formatDate = (value?: string) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
};

export function ProjectSelectionView() {
  const { data, refetch, isLoading } = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const { setProjectName, setSessionId, setCurrentStep, setScenarioTarget } = useSessionStore();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [scenarioTargetDraft, setScenarioTargetDraft] = useState(3);
  const [error, setError] = useState<string | null>(null);
  const [previewProject, setPreviewProject] = useState<string | null>(null);
  const [previewKey, setPreviewKey] = useState(0);

  const resetPreview = () => setPreviewProject(null);
  const togglePreview = (projectName: string) => {
    setPreviewProject((prev) => (prev === projectName ? null : projectName));
    setPreviewKey((k) => k + 1);
  };

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!name.trim()) throw new Error("Nom requis");
      await createProject({ name: name.trim(), description, scenario_target: scenarioTargetDraft });
      const session = await createSession(name.trim(), "project_selection", scenarioTargetDraft);
      setProjectName(name.trim());
      setSessionId(session.session_id);
      setCurrentStep("project_details");
      setScenarioTarget(scenarioTargetDraft);
      setName("");
      setDescription("");
      resetPreview();
      refetch();
      navigate("/step/project_details");
    }
  });

  const handleCreate = (evt: FormEvent) => {
    evt.preventDefault();
    setError(null);
    createMutation.mutate(undefined, {
      onError: (err) => setError((err as Error).message)
    });
  };

  const handleSelect = async (project: ProjectSummary) => {
    try {
      const session = await createSession(project.name, "project_selection", project.scenario_target);
      setProjectName(project.name);
      setSessionId(session.session_id);
      setCurrentStep("project_details");
      setScenarioTarget(project.scenario_target);
      resetPreview();
      navigate("/step/project_details");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="step-view">
      <h2>Créer ou sélectionner un projet</h2>
      <p>Chaque projet conserve ses audios finaux, scénarios et transcriptions.</p>
      {error && <p className="error">{error}</p>}

      <section className="card emphasis">
        <h3>Projets existants</h3>
        <p>Revenez sur un projet pour reprendre là où vous l’avez laissé. Les audios finalisés sont directement écoutables.</p>
        {isLoading ? (
          <p>Chargement...</p>
        ) : data && data.length > 0 ? (
          <ul className="project-list stacked">
            {data.map((project) => {
              const hasAudio = Boolean(project.final_audio?.path);
              const finalizedLabel = project.finalized_at ? formatDate(project.finalized_at) : null;
              return (
                <li key={project.name}>
                  <div
                    className="project-entry"
                    role="button"
                    tabIndex={0}
                    onClick={() => handleSelect(project)}
                    onKeyDown={(evt) => {
                      if (evt.key === "Enter" || evt.key === " ") handleSelect(project);
                    }}
                  >
                    <div className="project-label">
                      <strong>{project.name}</strong>{" "}
                      <small>({project.scenario_target} scénarios)</small>
                      {finalizedLabel && <span className="badge">Finalisé le {finalizedLabel}</span>}
                    </div>
                    {hasAudio && (
                      <button
                        type="button"
                        className="play-btn"
                        onClick={(evt) => {
                          evt.stopPropagation();
                          togglePreview(project.name);
                        }}
                      >
                        {previewProject === project.name ? "Pause" : "Écouter"}
                      </button>
                    )}
                  </div>
                  {hasAudio && previewProject === project.name && (
                    <audio
                      key={`${project.name}-${previewKey}`}
                      controls
                      autoPlay
                      className="project-audio-preview"
                      src={getProjectFinalAudioUrl(project.name)}
                      onClick={(evt) => evt.stopPropagation()}
                    />
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <p>Aucun projet enregistré pour le moment.</p>
        )}
      </section>

      <section className="card muted">
        <h3>Nouveau projet</h3>
        <form onSubmit={handleCreate} className="form-grid">
          <label>
            Nom
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ex: port_nantes" />
          </label>
          <label>
            Description
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} />
          </label>
          <label>
            Nombre de scénarios à générer (1 à 5)
            <input
              type="range"
              min={1}
              max={5}
              value={scenarioTargetDraft}
              onChange={(e) => setScenarioTargetDraft(Number(e.target.value))}
            />
            <span>{scenarioTargetDraft} scénario(s)</span>
          </label>
        <button type="submit" disabled={createMutation.isPending}>Créer</button>
        </form>
      </section>
    </div>
  );
}
