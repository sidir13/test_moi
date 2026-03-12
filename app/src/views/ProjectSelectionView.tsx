import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import {
  createProject,
  createSession,
  fetchProjects,
  ProjectSummary,
  getProjectFinalAudioUrl,
  getProjectFinalVideoUrl
} from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

type SessionBootstrap = {
  steps?: Record<string, unknown>;
  scenarios?: unknown[];
  selected_scenario?: unknown;
  scenario_audio?: { path?: string | null } | null;
};

const deriveProgressFromSession = (
  session: SessionBootstrap | null,
  requireFreshEdit: boolean
) => {
  const steps = (session?.steps ?? {}) as Record<string, unknown>;
  const storedScenarios = Array.isArray(session?.scenarios) ? (session?.scenarios as unknown[]) : [];
  const selectedScenario = session?.selected_scenario;
  const audioMeta = session?.scenario_audio;
  const audioSources = steps && typeof steps === "object" ? (steps as any).audio_sources : undefined;
  const transcriptionStepDone = Boolean(steps && (steps as any).transcription_review);
  const progressedBeyondTranscription =
    Boolean(
      (steps as any)?.scenario_review ||
        (steps as any)?.scenario_edit ||
        (steps as any)?.final_validation
    ) ||
    Boolean(selectedScenario) ||
    Boolean(audioMeta?.path);
  return {
    audioReady: Boolean(audioSources || audioMeta?.path),
    transcriptionsReviewed: transcriptionStepDone || progressedBeyondTranscription,
    scenariosReady: Boolean(storedScenarios.length > 0 || selectedScenario),
    scenarioChosen: Boolean(selectedScenario),
    scenarioEdited: requireFreshEdit ? false : Boolean(audioMeta?.path)
  };
};

const formatDate = (value?: string) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
};

const SpeakerIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path
      fill="currentColor"
      d="M5 9v6h4l5 5V4l-5 5H5zm11.5 3c0-1.77-1.02-3.29-2.5-4.03v8.06c1.48-.74 2.5-2.26 2.5-4.03z"
    />
  </svg>
);

const PauseIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path fill="currentColor" d="M6 5h4v14H6zm8 0h4v14h-4z" />
  </svg>
);

const VideoIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path
      fill="currentColor"
      d="M17 10.5V6c0-1.1-.9-2-2-2H5C3.9 4 3 4.9 3 6v12c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2v-4.5l4 4v-11l-4 4z"
    />
  </svg>
);

const DownloadIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path
      fill="currentColor"
      d="M5 20h14v-2H5v2zm7-18l-5.5 5.5h4v6h3v-6h4L12 2z"
    />
  </svg>
);

export function ProjectSelectionView() {
  const { data, refetch, isLoading } = useQuery({ queryKey: ["projects"], queryFn: fetchProjects });
  const {
    setProjectName,
    setSessionId,
    setCurrentStep,
    setScenarioTarget,
    lastProjectName,
    setLastProjectName,
    resetProgress,
    setProgress
  } = useSessionStore();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [scenarioTargetDraft, setScenarioTargetDraft] = useState(3);
  const [error, setError] = useState<string | null>(null);
  const [previewProject, setPreviewProject] = useState<string | null>(null);
  const [previewKey, setPreviewKey] = useState(0);
  const [videoProject, setVideoProject] = useState<string | null>(null);

  const resetPreview = () => setPreviewProject(null);
  const closeVideo = () => setVideoProject(null);
  const togglePreview = (projectName: string) => {
    setPreviewProject((prev) => (prev === projectName ? null : projectName));
    setPreviewKey((k) => k + 1);
  };

  const createMutation = useMutation({
    mutationFn: async () => {
      if (!name.trim()) throw new Error("Nom requis");
      const trimmed = name.trim();
      await createProject({ name: trimmed, description, scenario_target: scenarioTargetDraft });
      const session = await createSession(trimmed, "project_selection", scenarioTargetDraft);
      setProjectName(trimmed);
      setLastProjectName(trimmed);
      setSessionId(session.session_id);
      setCurrentStep("project_details");
      setScenarioTarget(scenarioTargetDraft);
      resetProgress();
      setName("");
      setDescription("");
      resetPreview();
      closeVideo();
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
      resetProgress();
      const session = await createSession(project.name, "project_selection", project.scenario_target);
      const derivedProgress = deriveProgressFromSession(session, Boolean(project.finalized_at));
      setProgress(derivedProgress);
      setProjectName(project.name);
      setLastProjectName(project.name);
      setSessionId(session.session_id);
      setCurrentStep("project_details");
      setScenarioTarget(project.scenario_target);
      resetPreview();
      closeVideo();
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
              const hasVideo = Boolean(project.final_slideshow?.path);
              const finalizedLabel = project.finalized_at ? formatDate(project.finalized_at) : null;
              const isLastActive = project.name === lastProjectName;
              return (
                <li key={project.name}>
                  <div
                    className={`project-entry${isLastActive ? " last-active" : ""}`}
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
                      <div className="project-label-badges">
                        {finalizedLabel && <span className="badge">Finalisé le {finalizedLabel}</span>}
                        {isLastActive && <span className="badge accent">Dernier projet actif</span>}
                      </div>
                    </div>
                    <div className="project-actions" style={{ display: "flex", gap: "0.25rem" }}>
                      {hasAudio && (
                        <button
                          type="button"
                          className="play-btn"
                          aria-label={
                            previewProject === project.name
                              ? "Mettre en pause l'audio final"
                              : "Écouter l'audio final"
                          }
                          onClick={(evt) => {
                            evt.stopPropagation();
                            togglePreview(project.name);
                          }}
                          data-playing={previewProject === project.name}
                        >
                          {previewProject === project.name ? <PauseIcon /> : <SpeakerIcon />}
                        </button>
                      )}
                      {hasAudio && (
                        <a
                          href={getProjectFinalAudioUrl(project.name)}
                          download
                          className="play-btn"
                          aria-label="Télécharger l'audio final"
                          onClick={(evt) => evt.stopPropagation()}
                        >
                          <DownloadIcon />
                        </a>
                      )}
                      {hasVideo && (
                        <button
                          type="button"
                          className="play-btn"
                          aria-label="Lire le diaporama vidéo"
                          onClick={(evt) => {
                            evt.stopPropagation();
                            setVideoProject(project.name);
                          }}
                        >
                          <VideoIcon />
                        </button>
                      )}
                      {hasVideo && (
                        <a
                          href={getProjectFinalVideoUrl(project.name)}
                          download
                          className="play-btn"
                          aria-label="Télécharger la vidéo finale"
                          onClick={(evt) => evt.stopPropagation()}
                        >
                          <DownloadIcon />
                        </a>
                      )}
                    </div>
                  </div>
                  {hasAudio && previewProject === project.name && (
                    <audio
                      key={`${project.name}-${previewKey}`}
                      controls
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
      {videoProject && (
        <div className="modal-backdrop" onClick={closeVideo}>
          <div className="modal" onClick={(evt) => evt.stopPropagation()}>
            <h3>Diaporama — {videoProject}</h3>
            <video
              key={videoProject}
              controls
              style={{ width: "100%", maxHeight: "70vh" }}
              src={getProjectFinalVideoUrl(videoProject)}
            />
            <button type="button" className="link" onClick={closeVideo}>
              Fermer
            </button>
          </div>
        </div>
      )}

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
