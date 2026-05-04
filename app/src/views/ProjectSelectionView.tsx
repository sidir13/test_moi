import { type FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  FolderOpen,
  Plus,
  Volume2,
  Pause,
  Video,
  Download,
  Loader2,
  MoreVertical,
  Sparkles
} from "lucide-react";

import {
  createProject,
  createSession,
  fetchProjects,
  type ProjectSummary,
  type ProjectWorkflowStatus,
  getProjectFinalAudioUrl,
  getProjectFinalVideoUrl
} from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type SessionBootstrap = {
  steps?: Record<string, unknown>;
  scenarios?: unknown[];
  selected_scenario?: unknown;
  scenario_audio?: { path?: string | null } | null;
};

const deriveProgressFromSession = (session: SessionBootstrap | null, requireFreshEdit: boolean) => {
  const steps = (session?.steps ?? {}) as Record<string, unknown>;
  const storedScenarios = Array.isArray(session?.scenarios) ? session.scenarios : [];
  const selectedScenario = session?.selected_scenario;
  const audioMeta = session?.scenario_audio;
  const audioSources = (steps as Record<string, unknown>).audio_sources;
  const transcriptionStepDone = Boolean((steps as Record<string, unknown>).transcription_review);
  const progressedBeyondTranscription =
    Boolean(
      (steps as Record<string, unknown>).scenario_review ||
        (steps as Record<string, unknown>).scenario_edit ||
        (steps as Record<string, unknown>).final_validation
    ) ||
    Boolean(selectedScenario) ||
    Boolean((audioMeta as { path?: string } | null)?.path);
  return {
    audioReady: Boolean(audioSources || (audioMeta as { path?: string } | null)?.path),
    transcriptionsReviewed: transcriptionStepDone || progressedBeyondTranscription,
    scenariosReady: Boolean(storedScenarios.length > 0 || selectedScenario),
    scenarioChosen: Boolean(selectedScenario),
    scenarioEdited: requireFreshEdit ? false : Boolean((audioMeta as { path?: string } | null)?.path)
  };
};

const formatDate = (value?: string) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
};

const formatAddedLong = (value?: string) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" });
};

const WORKFLOW_LABELS: Record<ProjectWorkflowStatus, string> = {
  termine: "Terminé",
  en_cours: "En cours",
  brouillon: "Brouillon"
};

function workflowBadgeVariant(status: ProjectWorkflowStatus | undefined): "success" | "warning" | "muted" {
  if (status === "termine") return "success";
  if (status === "en_cours") return "warning";
  return "muted";
}

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
  const [menuProject, setMenuProject] = useState<string | null>(null);
  const projectMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuProject) return;
    const onPointerDown = (e: MouseEvent) => {
      const el = projectMenuRef.current;
      if (el && !el.contains(e.target as Node)) setMenuProject(null);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [menuProject]);

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
      setPreviewProject(null);
      setVideoProject(null);
      refetch();
      navigate("/step/project_details");
    },
    onError: (err) => setError((err as Error).message)
  });

  const handleCreate = (evt: FormEvent) => {
    evt.preventDefault();
    setError(null);
    createMutation.mutate();
  };

  const bootstrapProjectSession = async (project: ProjectSummary) => {
    resetProgress();
    const session = await createSession(project.name, "project_selection", project.scenario_target);
    setProgress(deriveProgressFromSession(session, Boolean(project.finalized_at)));
    setProjectName(project.name);
    setLastProjectName(project.name);
    setSessionId(session.session_id);
    setCurrentStep("project_details");
    setScenarioTarget(project.scenario_target);
    setPreviewProject(null);
    setVideoProject(null);
    setMenuProject(null);
  };

  const handleSelect = async (project: ProjectSummary) => {
    try {
      setError(null);
      await bootstrapProjectSession(project);
      navigate("/step/project_details");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleViewArtifact = async (project: ProjectSummary) => {
    try {
      setError(null);
      await bootstrapProjectSession(project);
      const ws = project.workflow_status ?? "brouillon";
      if (ws === "termine") navigate("/step/final_validation");
      else if (ws === "en_cours") navigate("/step/scenario_review");
      else navigate("/step/project_details");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">Projets</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Créez un nouveau projet ou reprenez là où vous vous étiez arrêté.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4" />
            Projets existants
          </CardTitle>
          <CardDescription>
            Reprenez un projet pour continuer depuis là où vous l'avez laissé.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Chargement…
            </div>
          ) : data && data.length > 0 ? (
            <ul className="flex flex-col gap-4">
              {data.map((project) => {
                const hasAudio = Boolean(project.final_audio?.path);
                const hasVideo = Boolean(project.final_slideshow?.path);
                const finalizedLabel = project.finalized_at ? formatDate(project.finalized_at) : null;
                const isLastActive = project.name === lastProjectName;
                const nArtifacts = project.artifact_count ?? 0;
                const tags = project.tags ?? [];
                const wf = (project.workflow_status ?? "brouillon") as ProjectWorkflowStatus;
                const added = formatAddedLong(project.created_at);
                const loc = project.location?.trim();
                const metaLine = [loc, added ? `Ajouté le ${added}` : null].filter(Boolean).join(" • ");
                const desc =
                  project.description_preview?.trim() ||
                  "Aucune description pour l'instant — renseignez le contexte narratif dans Détails du projet.";
                const menuOpen = menuProject === project.name;

                return (
                  <li key={project.name} className="flex flex-col gap-2">
                    <Card
                      className={cn(
                        "overflow-hidden transition-shadow hover:shadow-md cursor-pointer",
                        isLastActive && "border-warning ring-1 ring-warning/30"
                      )}
                      role="button"
                      tabIndex={0}
                      onClick={() => void handleSelect(project)}
                      onKeyDown={(evt) => {
                        if (evt.key === "Enter" || evt.key === " ") {
                          evt.preventDefault();
                          void handleSelect(project);
                        }
                      }}
                    >
                      <CardContent className="p-4 flex flex-col gap-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2 min-w-0">
                            {nArtifacts > 0 ? (
                              <Badge
                                variant="outline"
                                className="gap-1 border-primary text-primary font-medium bg-background"
                              >
                                <Sparkles className="size-3.5 shrink-0" aria-hidden />
                                {nArtifacts} artefact{nArtifacts > 1 ? "s" : ""}
                              </Badge>
                            ) : null}
                            {project.has_k_graph ? (
                              <Badge
                                variant="outline"
                                className="gap-1 font-medium text-muted-foreground bg-background"
                              >
                                <Sparkles className="size-3.5 shrink-0" aria-hidden />
                                K-graph
                              </Badge>
                            ) : null}
                            {isLastActive ? (
                              <Badge variant="warning" className="font-medium">
                                Récent
                              </Badge>
                            ) : null}
                          </div>
                          <div
                            className="relative shrink-0"
                            ref={menuOpen ? projectMenuRef : null}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="size-9 text-foreground"
                              aria-expanded={menuOpen}
                              aria-haspopup="true"
                              aria-label="Plus d'actions"
                              onClick={() => setMenuProject((prev) => (prev === project.name ? null : project.name))}
                            >
                              <MoreVertical className="size-4" />
                            </Button>
                            {menuOpen ? (
                              <div
                                className="absolute right-0 top-full z-20 mt-1 w-56 rounded-lg border border-border bg-popover py-1 text-sm shadow-md"
                                role="menu"
                              >
                                {hasAudio ? (
                                  <button
                                    type="button"
                                    role="menuitem"
                                    className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-muted"
                                    onClick={() => {
                                      togglePreview(project.name);
                                      setMenuProject(null);
                                    }}
                                  >
                                    {previewProject === project.name ? (
                                      <Pause className="size-4 shrink-0" />
                                    ) : (
                                      <Volume2 className="size-4 shrink-0" />
                                    )}
                                    {previewProject === project.name ? "Pause audio" : "Écouter l'audio final"}
                                  </button>
                                ) : null}
                                {hasAudio ? (
                                  <a
                                    role="menuitem"
                                    href={getProjectFinalAudioUrl(project.name)}
                                    download
                                    className="flex w-full items-center gap-2 px-3 py-2 hover:bg-muted"
                                    onClick={() => setMenuProject(null)}
                                  >
                                    <Download className="size-4 shrink-0" />
                                    Télécharger l'audio
                                  </a>
                                ) : null}
                                {hasVideo ? (
                                  <button
                                    type="button"
                                    role="menuitem"
                                    className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-muted"
                                    onClick={() => {
                                      setVideoProject(project.name);
                                      setMenuProject(null);
                                    }}
                                  >
                                    <Video className="size-4 shrink-0" />
                                    Voir le diaporama
                                  </button>
                                ) : null}
                                {hasVideo ? (
                                  <a
                                    role="menuitem"
                                    href={getProjectFinalVideoUrl(project.name)}
                                    download
                                    className="flex w-full items-center gap-2 px-3 py-2 hover:bg-muted"
                                    onClick={() => setMenuProject(null)}
                                  >
                                    <Download className="size-4 shrink-0" />
                                    Télécharger la vidéo
                                  </a>
                                ) : null}
                                {!hasAudio && !hasVideo ? (
                                  <div className="px-3 py-2 text-muted-foreground">Aucun export final</div>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                        </div>

                        <div className="min-w-0 space-y-1">
                          <h3 className="text-xl font-semibold text-foreground leading-tight">{project.name}</h3>
                          <p className="text-xs text-muted-foreground">
                            {project.scenario_target} scénario{project.scenario_target > 1 ? "s" : ""} prévu
                            {project.scenario_target > 1 ? "s" : ""}
                          </p>
                        </div>

                        <p className="text-sm text-muted-foreground leading-[23px] line-clamp-4">{desc}</p>

                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant={workflowBadgeVariant(wf)} className="font-medium">
                            {WORKFLOW_LABELS[wf]}
                          </Badge>
                          {finalizedLabel ? (
                            <span className="text-xs text-muted-foreground">Finalisé le {finalizedLabel}</span>
                          ) : null}
                          {tags.map((tag) => (
                            <Badge key={tag} variant="muted" className="font-normal">
                              {tag}
                            </Badge>
                          ))}
                        </div>

                        {metaLine ? (
                          <p className="text-xs text-muted-foreground">{metaLine}</p>
                        ) : null}

                        <div className="flex gap-2 border-t border-border pt-3" onClick={(e) => e.stopPropagation()}>
                          <Button
                            type="button"
                            variant="outline"
                            className="flex-1 font-medium"
                            onClick={() => void handleSelect(project)}
                          >
                            Consulter l'archive
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            className="flex-1 border-primary font-medium text-primary hover:bg-secondary"
                            onClick={() => void handleViewArtifact(project)}
                          >
                            Voir artefact
                          </Button>
                        </div>
                      </CardContent>
                    </Card>

                    {hasAudio && previewProject === project.name ? (
                      <audio
                        key={`${project.name}-${previewKey}`}
                        controls
                        autoPlay
                        className="w-full rounded-lg border border-border bg-background px-2 py-1"
                        src={getProjectFinalAudioUrl(project.name)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground py-4">Aucun projet enregistré pour le moment.</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            Nouveau projet
          </CardTitle>
          <CardDescription>Définissez un nom et le nombre de scénarios à générer.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreate} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="project-name">Nom du projet</Label>
              <Input
                id="project-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ex: port_nantes_1905"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="project-desc">Description (optionnel)</Label>
              <Textarea
                id="project-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Quelques mots sur ce projet…"
              />
            </div>
            <Slider
              label="Nombre de scénarios à générer"
              valueLabel={`${scenarioTargetDraft} scénario${scenarioTargetDraft > 1 ? "s" : ""}`}
              min={1}
              max={5}
              value={scenarioTargetDraft}
              onChange={(e) => setScenarioTargetDraft(Number(e.target.value))}
            />
            <Button type="submit" disabled={createMutation.isPending} className="w-fit">
              {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Créer le projet
            </Button>
          </form>
        </CardContent>
      </Card>

      <Dialog open={Boolean(videoProject)} onOpenChange={(open) => !open && setVideoProject(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Diaporama — {videoProject}</DialogTitle>
          </DialogHeader>
          {videoProject && (
            <video
              key={videoProject}
              controls
              className="w-full max-h-[70vh] rounded-lg"
              src={getProjectFinalVideoUrl(videoProject)}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
