import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Circle, Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import { useSessionStore } from "@/hooks/useSessionStore";

export function StepNavigator() {
  const { steps, currentStep, setCurrentStep, language, progress } = useSessionStore();
  const navigate = useNavigate();

  const ordered = useMemo(
    () => steps.slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0)),
    [steps]
  );

  const currentIndex = ordered.findIndex((s) => s.id === currentStep);

  const isEnabled = (stepId: string): boolean => {
    switch (stepId) {
      case "project_selection":
      case "project_details":
        return true;
      case "audio_sources":
        return true;
      case "transcription_review":
        return progress.audioReady;
      case "configuration_scenario":
        return progress.audioReady;
      case "scenario_review":
        return progress.transcriptionsReviewed;
      case "choix_scenario":
        return progress.scenariosReady;
      case "scenario_edit":
        return progress.scenariosReady && progress.scenarioChosen;
      case "edition_text":
        return progress.scenarioChosen;
      case "final_validation":
        return progress.scenarioEdited;
      default:
        return true;
    }
  };

  return (
    <nav className="flex flex-col gap-1">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-2 mb-2">
        Étapes
      </p>
      {ordered.map((step, index) => {
        const isCurrent = step.id === currentStep;
        const isDone = currentIndex > -1 && index < currentIndex;
        const enabled = isEnabled(step.id);

        return (
          <button
            key={step.id}
            disabled={!enabled}
            onClick={() => {
              if (!enabled) return;
              setCurrentStep(step.id);
              navigate(step.id === ordered[0]?.id ? "/" : `/step/${step.id}`);
            }}
            className={cn(
              "group flex items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-all",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              isCurrent && "bg-primary/10 text-primary",
              isDone && !isCurrent && "text-success hover:bg-success-muted/70",
              !isCurrent && !isDone && enabled && "text-foreground hover:bg-accent",
              !enabled && "opacity-40 cursor-not-allowed"
            )}
          >
            <span
              className={cn(
                "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-xs font-semibold transition-colors",
                isCurrent && "border-primary bg-primary text-primary-foreground",
                isDone && !isCurrent && "border-success bg-success text-success-foreground",
                !isCurrent && !isDone && "border-border bg-background text-muted-foreground"
              )}
            >
              {isDone ? (
                <Check className="h-3 w-3" />
              ) : !enabled ? (
                <Lock className="h-2.5 w-2.5" />
              ) : (
                <Circle className="h-2 w-2 fill-current" />
              )}
            </span>

            <span className="flex flex-col gap-0.5 min-w-0">
              <span className="text-sm font-medium leading-tight truncate">
                {step.name?.[language] ?? step.id}
              </span>
              <span className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                {step.description?.[language]}
              </span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
