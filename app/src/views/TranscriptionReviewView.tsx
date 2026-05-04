import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { RefreshCw, Download, Save, ChevronRight, Loader2, AlertTriangle } from "lucide-react";

import {
  advanceStep,
  fetchProjectTranscriptions,
  fetchProjectKnowledgeGraph,
  updateProjectTranscription,
  type ProjectTranscription,
  API_BASE_URL
} from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

type SavePayload = { fileName: string; text: string };

export function TranscriptionReviewView() {
  const { projectName, sessionId, setCurrentStep, updateProgress } = useSessionStore();
  const navigate = useNavigate();

  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const dirtyRef = useRef<Record<string, boolean>>({});
  const [saveFeedback, setSaveFeedback] = useState<Record<string, string | null>>({});
  const [globalStatus, setGlobalStatus] = useState<string | null>(null);
  const [expandedSummaries, setExpandedSummaries] = useState<Record<string, boolean>>({});

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

  useEffect(() => { dirtyRef.current = dirty; }, [dirty]);

  useEffect(() => {
    const entries = transcriptionsQuery.data;
    if (!entries) return;
    setDrafts((prev) => {
      const next: Record<string, string> = {};
      entries.forEach((entry) => {
        next[entry.file_name] = dirtyRef.current[entry.file_name] && prev[entry.file_name] !== undefined
          ? prev[entry.file_name]
          : entry.transcription;
      });
      return next;
    });
    setDirty((current) => {
      const filtered: Record<string, boolean> = {};
      entries.forEach((entry) => { filtered[entry.file_name] = current[entry.file_name] ?? false; });
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
      setSaveFeedback((prev) => ({ ...prev, [data.file_name]: "Enregistré" }));
      transcriptionsQuery.refetch();
    },
    onError: (err, variables) => {
      if (variables?.fileName) {
        setSaveFeedback((prev) => ({ ...prev, [variables.fileName]: (err as Error).message }));
      }
    }
  });

  const transcriptions = useMemo<ProjectTranscription[]>(
    () => transcriptionsQuery.data ?? [],
    [transcriptionsQuery.data]
  );

  if (!projectName || !sessionId) {
    return <p className="text-sm text-muted-foreground">Sélectionnez un projet et une session pour réviser vos transcriptions.</p>;
  }

  const handleChange = (fileName: string, value: string) => {
    setDrafts((prev) => ({ ...prev, [fileName]: value }));
    setDirty((prev) => ({ ...prev, [fileName]: true }));
    setSaveFeedback((prev) => ({ ...prev, [fileName]: null }));
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
    setGlobalStatus("Enregistrement…");
    try {
      await advanceStep(sessionId, "transcription_review", {
        files: transcriptions.map((t) => t.file_name)
      });
      updateProgress({ transcriptionsReviewed: true });
      setCurrentStep("scenario_review");
      navigate("/step/scenario_review");
    } catch (err) {
      setGlobalStatus((err as Error).message);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Révision des transcriptions</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Vérifiez et corrigez les transcriptions automatiques avant la génération des scénarios.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => transcriptionsQuery.refetch()}
          disabled={transcriptionsQuery.isFetching}
        >
          <RefreshCw className={cn("mr-2 h-3.5 w-3.5", transcriptionsQuery.isFetching && "animate-spin")} />
          Actualiser
        </Button>
      </div>

      {transcriptionsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Chargement des transcriptions…
        </div>
      )}

      {!transcriptionsQuery.isLoading && transcriptions.length === 0 && (
        <Card>
          <CardContent className="pt-5">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-4 w-4 text-warning mt-0.5 shrink-0" />
              <p className="text-sm text-muted-foreground">
                Aucune transcription disponible. Vérifiez que vos pistes vocales ont bien été analysées.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {transcriptions.map((entry) => {
        const currentText = drafts[entry.file_name] ?? entry.transcription;
        const isDirty = dirty[entry.file_name];
        const feedback = saveFeedback[entry.file_name];
        const summaryExpanded = expandedSummaries[entry.file_name] ?? false;

        return (
          <Card key={entry.file_name}>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <CardTitle className="text-base">{entry.file_name}</CardTitle>
                  {entry.source && (
                    <CardDescription>{entry.source}</CardDescription>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {isDirty && (
                    <Badge variant="warning" className="text-xs">
                      <AlertTriangle className="mr-1 h-2.5 w-2.5" />
                      Non sauvegardé
                    </Badge>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {entry.summary && (
                <div>
                  <button
                    type="button"
                    className="text-xs font-medium text-primary hover:underline"
                    onClick={() => setExpandedSummaries((p) => ({ ...p, [entry.file_name]: !summaryExpanded }))}
                  >
                    {summaryExpanded ? "Masquer le résumé" : "Résumé automatique"}
                  </button>
                  {summaryExpanded && (
                    <div className="mt-2 rounded-lg bg-muted/50 p-3 text-sm flex flex-col gap-2">
                      {entry.summary.global_summary && (
                        <p>{entry.summary.global_summary}</p>
                      )}
                      {entry.summary.topics && entry.summary.topics.length > 0 && (
                        <ul className="list-disc pl-4 space-y-1">
                          {entry.summary.topics.map((topic, idx) => (
                            <li key={`${entry.file_name}-topic-${idx}`} className="text-xs">
                              <span className="font-medium">{topic.title} :</span> {topic.summary}
                              {topic.keywords && topic.keywords.length > 0 && (
                                <span className="text-muted-foreground"> — {topic.keywords.join(", ")}</span>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              )}

              <Textarea
                rows={8}
                value={currentText}
                onChange={(e) => handleChange(entry.file_name, e.target.value)}
                placeholder="Transcription…"
              />

              <div className="flex items-center gap-2 flex-wrap">
                <Button
                  type="button"
                  size="sm"
                  variant={isDirty ? "default" : "outline"}
                  onClick={() => saveMutation.mutate({ fileName: entry.file_name, text: drafts[entry.file_name] ?? "" })}
                  disabled={saveMutation.isPending}
                >
                  <Save className="mr-1.5 h-3.5 w-3.5" />
                  Enregistrer
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => handleExport(entry.file_name)}
                >
                  <Download className="mr-1.5 h-3.5 w-3.5" />
                  Exporter (.txt)
                </Button>
                {feedback && (
                  <span className={cn("text-xs", feedback.includes("Enregistré") ? "text-green-600" : "text-destructive")}>
                    {feedback}
                  </span>
                )}
              </div>
            </CardContent>
          </Card>
        );
      })}

      {/* Knowledge graph events table */}
      {graphQuery.data && graphQuery.data.events.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Événements identifiés</CardTitle>
            <CardDescription>Extraits automatiquement des transcriptions.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    {["Période", "Événement", "Acteurs", "Lieux"].map((h) => (
                      <th key={h} className="text-left px-2 py-2 font-medium text-muted-foreground text-xs uppercase tracking-wider">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {graphQuery.data.events.map((ev, idx) => (
                    <tr key={idx} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                      <td className="px-2 py-2.5 text-xs text-muted-foreground whitespace-nowrap">{ev.approximate_time ?? "—"}</td>
                      <td className="px-2 py-2.5">
                        <p className="font-medium">{ev.title}</p>
                        {ev.description && <p className="text-xs text-muted-foreground mt-0.5">{ev.description}</p>}
                      </td>
                      <td className="px-2 py-2.5 text-xs">{ev.actors?.join(", ") ?? "—"}</td>
                      <td className="px-2 py-2.5 text-xs">{ev.places?.join(", ") ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Knowledge graph iframe */}
      {graphQuery.data && graphQuery.data.graph.nodes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Graphe de connaissances</CardTitle>
          </CardHeader>
          <CardContent>
            <iframe
              src={`${API_BASE_URL}/projects/${encodeURIComponent(projectName)}/knowledge-graph-view`}
              className="w-full h-[600px] rounded-lg border-0"
              title="Graphe de connaissances"
            />
          </CardContent>
        </Card>
      )}

      <Separator />

      <form onSubmit={handleContinue}>
        {globalStatus && (
          <Alert variant={globalStatus.includes("Enregistrement") ? "info" : "destructive"} className="mb-4">
            <AlertDescription>{globalStatus}</AlertDescription>
          </Alert>
        )}
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={transcriptions.length === 0 || saveMutation.isPending}>
            Continuer vers les scénarios
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
          {transcriptions.length === 0 && (
            <p className="text-sm text-muted-foreground">Au moins une transcription est requise.</p>
          )}
        </div>
      </form>
    </div>
  );
}
