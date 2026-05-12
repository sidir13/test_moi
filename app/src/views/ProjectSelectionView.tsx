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
  Trash2,
  Search,
  ListFilter,
  Upload,
  ChevronRight
} from "lucide-react";

import {
  createProject,
  deleteProject,
  uploadAudio,
  createSession,
  fetchProjects,
  type ProjectSummary,
  type ProjectWorkflowStatus,
  getProjectFinalAudioUrl,
  getProjectFinalVideoUrl
} from "@/api/client";
import loadingIconUrl from "@/assets/svg/laoding.svg?url";
import loadingBlueIconUrl from "@/assets/svg/loading-blue.svg?url";
import { useSessionStore } from "@/hooks/useSessionStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
  return "en_cours";
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
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [archiveSearch, setArchiveSearch] = useState("");
  const [createArchiveOpen, setCreateArchiveOpen] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

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
      if (selectedFiles.length > 0) {
        await Promise.all(selectedFiles.map((file) => uploadAudio(trimmed, file)));
      }
      const session = await createSession(trimmed, "project_selection", scenarioTargetDraft);
      setProjectName(trimmed);
      setLastProjectName(trimmed);
      setSessionId(session.session_id);
      setCurrentStep("project_details");
      setScenarioTarget(scenarioTargetDraft);
      resetProgress();
      setName("");
      setPreviewProject(null);
      setVideoProject(null);
      setCreateArchiveOpen(false);
      setSelectedFiles([]);
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

  const handleAddArchiveClick = () => setCreateArchiveOpen(true);

  const pickFiles = () => fileInputRef.current?.click();

  const onFilesSelected = (evt: React.ChangeEvent<HTMLInputElement>) => {
    const list = Array.from(evt.target.files ?? []);
    setSelectedFiles(list);
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
      <div className="flex w-full max-w-none flex-col gap-6">
        <div className="-mx-6 flex flex-col gap-3 px-4 sm:flex-row sm:items-center sm:justify-between sm:gap-10 sm:px-5">
          <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-center sm:gap-3 sm:pl-4 sm:pr-6">
            <div className="relative min-w-0 flex-1 sm:max-w-[360px]">
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
          <Button
            type="button"
            onClick={handleAddArchiveClick}
            className="h-[38px] w-fit shrink-0 gap-2 rounded-[12px] bg-primary px-4 text-primary-foreground hover:bg-primary/90"
            aria-label="Ajouter une archive"
          >
            <Plus className="size-4 shrink-0" />
            Ajouter une archive
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
          <ul className="mt-20 grid grid-cols-1 gap-y-5 sm:grid-cols-[repeat(2,minmax(0,560px))] sm:justify-center sm:gap-x-5">
              {filteredProjects.map((project) => {
                const hasAudio = Boolean(project.final_audio?.path);
                const hasVideo = Boolean(project.final_slideshow?.path);
                const archiveDownloadUrl = hasAudio
                  ? getProjectFinalAudioUrl(project.name)
                  : hasVideo
                    ? getProjectFinalVideoUrl(project.name)
                    : undefined;
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
                  <li key={project.name} className="flex w-full min-w-0 flex-col gap-1 sm:w-[560px]">
                    <Card
                      className={cn(
                        "overflow-hidden p-0 transition-shadow hover:shadow-md cursor-pointer min-h-[330px]"
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
                        className="h-1.5 w-full shrink-0"
                        style={{ backgroundColor: cardTopAccentHex(project.name) }}
                        aria-hidden
                      />
                      <CardContent className="flex h-full flex-col gap-3 p-4">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2 min-w-0">
                            <Badge
                              variant="outline"
                              className="h-[33.6px] gap-1 rounded-[12px] border border-primary bg-[#F4F4F4] px-3 py-[5px] font-medium text-primary"
                            >
                              <img src={loadingBlueIconUrl} alt="" className="size-3.5 shrink-0" aria-hidden />
                              {mockArtifacts} artefact{mockArtifacts > 1 ? "s" : ""}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="h-[33.6px] gap-1 rounded-[12px] border border-[#C3C3C3] bg-[#F4F4F4] px-3 py-[5px] font-medium text-muted-foreground"
                            >
                              <img src={loadingIconUrl} alt="" className="size-3.5 shrink-0" aria-hidden />
                              K-graph
                            </Badge>
                          </div>
                          <div
                            className="relative shrink-0"
                            ref={menuOpen ? projectMenuRef : null}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Button
                              type="button"
                              variant="ghost"
                              className="size-[33.6px] rounded-[10px] border border-[#C3C3C3] bg-background text-foreground hover:bg-muted/70"
                              aria-expanded={menuOpen}
                              aria-haspopup="true"
                              aria-label="Plus d'actions"
                              onClick={() => setMenuProject((prev) => (prev === project.name ? null : project.name))}
                            >
                              <MoreVertical className="size-4" />
                            </Button>
                            {menuOpen ? (
                              <div
                                className="absolute right-0 top-full z-20 mt-2 w-[240px] overflow-hidden rounded-[8px] border border-[#E2E8F0] bg-background text-sm shadow-[0_2px_10px_rgba(0,0,0,0.10)]"
                                role="menu"
                              >
                                {archiveDownloadUrl ? (
                                  <a
                                    role="menuitem"
                                    href={archiveDownloadUrl}
                                    download
                                    className="flex h-[57px] w-full items-center gap-2 px-3 py-2 text-base font-normal text-foreground hover:bg-muted"
                                    onClick={() => setMenuProject(null)}
                                  >
                                    <Download className="size-4 shrink-0" />
                                    Télécharger l'archive
                                  </a>
                                ) : (
                                  <button
                                    type="button"
                                    role="menuitem"
                                    className="flex h-[57px] w-full items-center gap-2 px-3 py-2 text-left text-foreground/50"
                                    disabled
                                  >
                                    <Download className="size-4 shrink-0" />
                                    Télécharger l'archive
                                  </button>
                                )}
                                <button
                                  type="button"
                                  role="menuitem"
                                  className="flex h-[57px] w-full items-center gap-2 border-t border-[#E2E8F0] px-3 py-2 text-left text-[#FF1700] hover:bg-muted"
                                  onClick={async () => {
                                    setMenuProject(null);
                                    try {
                                      setError(null);
                                      await deleteProject(project.name);
                                      if (lastProjectName === project.name) {
                                        setLastProjectName(undefined);
                                      }
                                      await refetch();
                                    } catch (err) {
                                      setError((err as Error).message);
                                    }
                                  }}
                                >
                                  <Trash2 className="size-4 shrink-0" />
                                  Supprimer
                                </button>
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
                          className="-mx-4 -mb-4 mt-auto flex gap-2 rounded-b-xl border-t border-border bg-[#F4F4F4] px-4 pb-4 pt-3"
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
                          {displayWf !== "en_cours" ? (
                            <Button
                              type="button"
                              variant="outline"
                              className="h-11 flex-1 rounded-lg border-primary font-medium text-primary hover:bg-secondary"
                              onClick={() => void handleViewArtifact(project)}
                            >
                              Voir artefact
                            </Button>
                          ) : null}
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

        {/* <Card>Nouveau projet</Card> replaced by modal flow */}

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

        <Dialog open={createArchiveOpen} onOpenChange={setCreateArchiveOpen}>
          <DialogContent className="w-[622px] max-w-[95vw] min-h-[490px] gap-[10px] rounded-[18px] border border-[#E2E8F0] bg-background p-6 shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
            <DialogHeader className="space-y-2">
              <DialogTitle className="h-[29px] w-[197px] text-[24px] font-semibold leading-[100%] text-foreground">
                Nouvelle Archive
              </DialogTitle>
            </DialogHeader>

            <form onSubmit={handleCreate} className="flex flex-col gap-5">
              <div className="flex flex-col gap-2">
                <Label htmlFor="project-name-modal" className="text-[14px] font-semibold text-foreground">
                  Nom de l’archive
                </Label>
                <Input
                  id="project-name-modal"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ex: Collection Seconde Guerre Mondiale"
                  className="h-11 rounded-[10px] border border-border bg-[#F4F4F4] text-sm text-foreground"
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label className="text-[14px] font-semibold text-foreground">
                  Fichiers audio principaux <span className="text-destructive">*</span>
                </Label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".mp3,.wav,.m4a,audio/*"
                  multiple
                  className="hidden"
                  onChange={onFilesSelected}
                />
                <button
                  type="button"
                  onClick={pickFiles}
                  className="flex min-h-[230px] w-full flex-col items-center justify-center gap-3 rounded-[14px] border border-dashed border-primary/40 bg-background px-6 py-8 text-center hover:bg-muted/30"
                >
                  <Upload className="size-10 text-muted-foreground" />
                  <div className="space-y-1">
                    <p className="text-base font-medium text-[#45556C]">Cliquez pour télécharger</p>
                    <p className="text-sm text-muted-foreground">MP3, WAV, M4A jusqu’à 100MB</p>
                  </div>
                  {selectedFiles.length > 0 ? (
                    <p className="text-xs text-muted-foreground">{selectedFiles.length} fichier(s) sélectionné(s)</p>
                  ) : null}
                </button>
              </div>

              <div className="flex justify-end">
                <Button
                  type="submit"
                  disabled={createMutation.isPending || !name.trim() || selectedFiles.length === 0}
                  className="h-[46px] rounded-[14px] bg-primary px-6 text-base font-medium text-primary-foreground hover:bg-primary/90"
                >
                  {createMutation.isPending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                  Suivant
                  <ChevronRight className="ml-1 size-4" />
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}
