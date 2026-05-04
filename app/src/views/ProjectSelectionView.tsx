import { type FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { FolderOpen, Plus, Volume2, Pause, Video, Download, Loader2 } from "lucide-react";

import {
  createProject,
  createSession,
  fetchProjects,
  type ProjectSummary,
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

  const handleSelect = async (project: ProjectSummary) => {
    try {
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
      navigate("/step/project_details");
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Projets</h2>
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
            <ul className="flex flex-col gap-2">
              {data.map((project) => {
                const hasAudio = Boolean(project.final_audio?.path);
                const hasVideo = Boolean(project.final_slideshow?.path);
                const finalizedLabel = project.finalized_at ? formatDate(project.finalized_at) : null;
                const isLastActive = project.name === lastProjectName;
                return (
                  <li key={project.name}>
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => handleSelect(project)}
                      onKeyDown={(evt) => {
                        if (evt.key === "Enter" || evt.key === " ") handleSelect(project);
                      }}
                      className={cn(
                        "flex items-center justify-between rounded-lg border px-4 py-3 cursor-pointer transition-all",
                        "hover:border-primary hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        isLastActive && "border-orange-400 bg-orange-50/50"
                      )}
                    >
                      <div className="flex flex-col gap-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-medium text-sm">{project.name}</span>
                          <span className="text-xs text-muted-foreground">
                            ({project.scenario_target} scénarios)
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {finalizedLabel && (
                            <Badge variant="success">Finalisé le {finalizedLabel}</Badge>
                          )}
                          {isLastActive && (
                            <Badge variant="warning">Dernier projet actif</Badge>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-1 ml-3 shrink-0">
                        {hasAudio && (
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            aria-label={previewProject === project.name ? "Pause" : "Écouter l'audio final"}
                            onClick={(e) => { e.stopPropagation(); togglePreview(project.name); }}
                            className="h-8 w-8"
                          >
                            {previewProject === project.name ? (
                              <Pause className="h-4 w-4" />
                            ) : (
                              <Volume2 className="h-4 w-4" />
                            )}
                          </Button>
                        )}
                        {hasAudio && (
                          <Button
                            variant="outline"
                            size="icon"
                            asChild
                            className="h-8 w-8"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <a
                              href={getProjectFinalAudioUrl(project.name)}
                              download
                              aria-label="Télécharger l'audio final"
                            >
                              <Download className="h-4 w-4" />
                            </a>
                          </Button>
                        )}
                        {hasVideo && (
                          <Button
                            type="button"
                            variant="outline"
                            size="icon"
                            aria-label="Voir le diaporama"
                            onClick={(e) => { e.stopPropagation(); setVideoProject(project.name); }}
                            className="h-8 w-8"
                          >
                            <Video className="h-4 w-4" />
                          </Button>
                        )}
                        {hasVideo && (
                          <Button
                            variant="outline"
                            size="icon"
                            asChild
                            className="h-8 w-8"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <a
                              href={getProjectFinalVideoUrl(project.name)}
                              download
                              aria-label="Télécharger la vidéo"
                            >
                              <Download className="h-4 w-4" />
                            </a>
                          </Button>
                        )}
                      </div>
                    </div>

                    {hasAudio && previewProject === project.name && (
                      <audio
                        key={`${project.name}-${previewKey}`}
                        controls
                        autoPlay
                        className="w-full mt-2 rounded-lg"
                        src={getProjectFinalAudioUrl(project.name)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    )}
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
