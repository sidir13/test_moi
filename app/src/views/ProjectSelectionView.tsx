import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Plus,
  Volume2,
  Pause,
  Video,
  Download,
  Loader2,
  MoreVertical,
  Search,
  ListFilter
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
import loadingIconUrl from "@/assets/svg/laoding.svg?url";
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

/** Couleurs brand / system (design system) — bandeau haut de carte, stable par nom de projet */
const CARD_TOP_ACCENT_HEX = [
  "#007AFF",
  "#FFA202",
  "#C8009C",
  "#623DC7",
  "#04A404",
  "#92B2FF",
  "#45556C"
] as const;

function stringHash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

function cardTopAccentHex(projectName: string): string {
  return CARD_TOP_ACCENT_HEX[stringHash(projectName) % CARD_TOP_ACCENT_HEX.length];
}

/** Pastille artefacts — mock déterministe (1–3) en attendant le compteur métier */
function mockArtifactCount(projectName: string): number {
  return 1 + (stringHash(`${projectName}:art`) % 3);
}

const RECENT_INCOMPLETE_MAX_DAYS = 30;

function isRecentNotFinalized(project: ProjectSummary): boolean {
  if (project.finalized_at) return false;
  if (!project.created_at) return false;
  const created = new Date(project.created_at);
  if (Number.isNaN(created.getTime())) return false;
  const ageDays = (Date.now() - created.getTime()) / 86400000;
  return ageDays >= 0 && ageDays <= RECENT_INCOMPLETE_MAX_DAYS;
}

/** Statut affiché sur la carte (récent + non finalisé → En cours, jaune) */
function getCardWorkflowStatus(project: ProjectSummary): ProjectWorkflowStatus {
  if (project.finalized_at) return "termine";
  const wf = (project.workflow_status ?? "brouillon") as ProjectWorkflowStatus;
  if (wf === "en_cours") return "en_cours";
  if (isRecentNotFinalized(project)) return "en_cours";
  return "brouillon";
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
  const [archiveSearch, setArchiveSearch] = useState("");

  const projects = data ?? [];
  const filteredProjects = useMemo(() => {
    const q = archiveSearch.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((p) => {
      const inName = p.name.toLowerCase().includes(q);
      const inNotes = (p.description_preview ?? "").toLowerCase().includes(q);
      const inTags = (p.tags ?? []).some((t) => t.toLowerCase().includes(q));
      const inLoc = (p.location ?? "").toLowerCase().includes(q);
      return inName || inNotes || inTags || inLoc;
    });
  }, [projects, archiveSearch]);

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
    <div className="-m-6 min-h-full bg-[#F4F4F4] px-6 py-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
          <div className="relative min-w-0 flex-1">
            <Input
              type="search"
              value={archiveSearch}
              onChange={(e) => setArchiveSearch(e.target.value)}
              placeholder="Rechercher une archive…"
              aria-label="Rechercher une archive"
              className="h-10 rounded-full border-border bg-background pr-10 pl-4 text-sm shadow-sm"
            />
            <Search
              className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden
            />
          </div>
          <Button
            type="button"
            variant="outline"
            className="h-10 shrink-0 gap-2 rounded-full border-border bg-background px-4 font-medium shadow-sm sm:self-stretch"
            aria-label="Filtrer les archives"
          >
            Filtrer
            <ListFilter className="size-4 shrink-0" aria-hidden />
          </Button>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {isLoading ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Chargement…
          </div>
        ) : projects.length > 0 ? (
          filteredProjects.length > 0 ? (
          <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {filteredProjects.map((project) => {
                const hasAudio = Boolean(project.final_audio?.path);
                const hasVideo = Boolean(project.final_slideshow?.path);
                const isLastActive = project.name === lastProjectName;
                const mockArtifacts = mockArtifactCount(project.name);
                const tags = project.tags ?? [];
                const displayWf = getCardWorkflowStatus(project);
                const addedLong = formatAddedLong(project.created_at);
                const finalizedLong = formatAddedLong(project.finalized_at);
                const loc = project.location?.trim();
                const desc =
                  project.description_preview?.trim() ||
                  "Aucune description pour l'instant — renseignez le contexte narratif dans Détails du projet.";
                const menuOpen = menuProject === project.name;

                return (
                  <li key={project.name} className="flex min-w-0 flex-col gap-2">
                    <Card
                      className={cn(
                        "overflow-hidden p-0 transition-shadow hover:shadow-md cursor-pointer",
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
                      <div
                        className="h-1 w-full shrink-0"
                        style={{ backgroundColor: cardTopAccentHex(project.name) }}
                        aria-hidden
                      />
                      <CardContent className="flex flex-col gap-3 p-4">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2 min-w-0">
                            <Badge
                              variant="outline"
                              className="gap-1 border-primary bg-background font-medium text-primary"
                            >
                              <img src={loadingIconUrl} alt="" className="size-3.5 shrink-0" aria-hidden />
                              {mockArtifacts} artefact{mockArtifacts > 1 ? "s" : ""}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="gap-1 bg-background font-medium text-muted-foreground"
                            >
                              <img src={loadingIconUrl} alt="" className="size-3.5 shrink-0" aria-hidden />
                              K-graph
                            </Badge>
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

                        <div className="min-w-0">
                          <h3 className="text-xl font-semibold leading-tight text-foreground">{project.name}</h3>
                        </div>

                        <p className="text-sm text-muted-foreground leading-[23px] line-clamp-4">{desc}</p>

                        <div className="flex flex-wrap items-center gap-2">
                          <Badge
                            variant={workflowBadgeVariant(displayWf)}
                            className={cn(
                              "font-medium",
                              displayWf === "termine" && "border border-success bg-success-muted"
                            )}
                          >
                            {WORKFLOW_LABELS[displayWf]}
                          </Badge>
                          {tags.map((tag) => (
                            <Badge key={tag} variant="muted" className="font-normal">
                              {tag}
                            </Badge>
                          ))}
                        </div>

                        <div className="flex flex-col gap-1 text-xs text-muted-foreground">
                          {loc || addedLong ? (
                            <p>
                              {loc ? <span>{loc}</span> : null}
                              {loc && addedLong ? <span className="text-muted-foreground/80">{" • "}</span> : null}
                              {addedLong ? <span>Ajouté le {addedLong}</span> : null}
                            </p>
                          ) : null}
                          {finalizedLong ? (
                            <p>
                              <span>Finalisé le {finalizedLong}</span>
                            </p>
                          ) : null}
                        </div>

                        <div
                          className="-mx-4 -mb-4 mt-1 flex gap-2 rounded-b-xl border-t border-border bg-[#F4F4F4] px-4 pb-4 pt-3"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Button
                            type="button"
                            variant="outline"
                            className="h-11 flex-1 rounded-lg font-medium"
                            onClick={() => void handleSelect(project)}
                          >
                            Consulter l'archive
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            className="h-11 flex-1 rounded-lg border-primary font-medium text-primary hover:bg-secondary"
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
            <p className="text-sm text-muted-foreground py-2">Aucun résultat pour cette recherche.</p>
          )
        ) : (
          <p className="text-sm text-muted-foreground py-2">Aucun projet enregistré pour le moment.</p>
        )}

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
    </div>
  );
}
