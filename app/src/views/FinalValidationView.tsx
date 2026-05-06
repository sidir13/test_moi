import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2, ArrowLeft, Archive, Loader2 } from "lucide-react";

import { advanceStep } from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";

export function FinalValidationView() {
  const {
    projectName,
    sessionId,
    setProjectName,
    setSessionId,
    setCurrentStep,
    resetProgress
  } = useSessionStore();
  const navigate = useNavigate();

  const [modalOpen, setModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirm = async () => {
    if (!sessionId) return;
    setIsLoading(true);
    setError(null);
    try {
      await advanceStep(sessionId, "final_validation", { confirmed: true });
      resetProgress();
      setSessionId(undefined);
      setProjectName(undefined);
      setCurrentStep("project_selection");
      setModalOpen(false);
      navigate("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-xl">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">Validation finale</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Archivez le projet et verrouillez le scénario final.
        </p>
      </div>

      <Card className="border-success/30 bg-success-muted/80">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-success">
            <CheckCircle2 className="h-5 w-5" />
            Projet prêt à être finalisé
          </CardTitle>
          <CardDescription className="text-foreground">
            Projet : <strong>{projectName ?? "—"}</strong>
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-foreground space-y-2">
          <p>
            En confirmant, vous archivez l'audio et les métadonnées dans{" "}
            <code className="rounded bg-background/80 border border-border px-1.5 py-0.5 font-mono text-xs">
              {projectName ? `data/projects/${projectName}/config.json` : "la configuration du projet"}
            </code>
            .
          </p>
          <p>
            Vous pouvez revenir aux étapes précédentes pour ajuster le scénario avant de finaliser.
          </p>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex gap-3">
        <Button
          variant="outline"
          onClick={() => navigate("/step/scenario_edit")}
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour à l'édition
        </Button>
        <Button onClick={() => setModalOpen(true)}>
          <Archive className="mr-2 h-4 w-4" />
          Confirmer la finalisation
        </Button>
      </div>

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Confirmer la finalisation</DialogTitle>
            <DialogDescription>
              Voulez-vous archiver le projet <strong>{projectName}</strong> et verrouiller son scénario final ?
              Cette action peut être refaite en repartant d'un nouveau projet.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setModalOpen(false)} disabled={isLoading}>
              Annuler
            </Button>
            <Button onClick={confirm} disabled={isLoading}>
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Confirmer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
