import { Component, useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Outlet, Route, Routes, useParams } from "react-router-dom";

import { fetchSteps, fetchStepConfig } from "./api/client";
import { StepNavigator } from "./components/StepNavigator";
import { FlagToggle } from "./components/FlagToggle";
import { ChatPanel } from "./components/ChatPanel";
import { WaveformPanel } from "./components/WaveformPanel";
import { useSessionStore } from "./hooks/useSessionStore";
import { ProjectSelectionView } from "./views/ProjectSelectionView";
import { ProjectDetailsView } from "./views/ProjectDetailsView";
import { AudioSelectionView } from "./views/AudioSelectionView";
import { TranscriptionReviewView } from "./views/TranscriptionReviewView";
import { ScenarioReviewView } from "./views/ScenarioReviewView";
import { ScenarioEditView } from "./views/ScenarioEditView";
import { FinalValidationView } from "./views/FinalValidationView";

type StepId =
  | "project_selection"
  | "project_details"
  | "audio_sources"
  | "transcription_review"
  | "scenario_review"
  | "scenario_edit"
  | "final_validation";

const STEP_COMPONENTS: Record<StepId, React.ComponentType> = {
  project_selection: ProjectSelectionView,
  project_details: ProjectDetailsView,
  audio_sources: AudioSelectionView,
  transcription_review: TranscriptionReviewView,
  scenario_review: ScenarioReviewView,
  scenario_edit: ScenarioEditView,
  final_validation: FinalValidationView
};

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center h-full gap-3 p-8 text-center">
          <p className="text-destructive font-semibold">Une erreur inattendue s'est produite.</p>
          <p className="text-sm text-muted-foreground">{(this.state.error as Error).message}</p>
          <button
            className="text-sm text-primary underline"
            onClick={() => this.setState({ error: null })}
          >
            Réessayer
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function Layout() {
  const { setSteps, currentStep } = useSessionStore();
  const { data: stepsResponse } = useQuery({ queryKey: ["steps"], queryFn: fetchSteps });

  useEffect(() => {
    if (stepsResponse?.steps) {
      setSteps(stepsResponse.steps);
    }
  }, [stepsResponse, setSteps]);

  const showChat =
    currentStep &&
    currentStep !== "project_selection" &&
    currentStep !== "final_validation";

  return (
    <div className="flex flex-col min-h-screen bg-slate-50">
      <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-border shadow-sm shrink-0">
        <div>
          <h1 className="text-base font-bold text-foreground leading-tight">Mémoire des Territoires</h1>
          <p className="text-xs text-muted-foreground">NotebookLM pour archives sonores historiques</p>
        </div>
        <FlagToggle />
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-64 shrink-0 border-r border-border bg-white overflow-y-auto p-4">
          <StepNavigator />
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>

        {showChat && (
          <aside className="w-80 shrink-0 border-l border-border bg-white overflow-hidden flex flex-col">
            <ChatPanel />
          </aside>
        )}
      </div>

      <footer className="shrink-0 border-t border-border bg-white">
        <WaveformPanel />
      </footer>
    </div>
  );
}

function Placeholder({ stepId }: { stepId: string }) {
  const { language, chatPlaceholder, setChatPlaceholder, steps } = useSessionStore();
  const { data } = useQuery({
    queryKey: ["step", stepId],
    queryFn: () => fetchStepConfig(stepId),
    enabled: Boolean(stepId)
  });
  const fallback = steps.find((s) => s.id === stepId);
  const localizedPlaceholder =
    data?.chat_placeholder?.[language] ?? fallback?.chat_placeholder?.[language];

  useEffect(() => {
    if (localizedPlaceholder) setChatPlaceholder(localizedPlaceholder);
  }, [localizedPlaceholder, setChatPlaceholder]);

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-xl font-semibold">
        {data?.name?.[language] ?? fallback?.name?.[language] ?? stepId}
      </h2>
      <p className="text-sm text-muted-foreground">{data?.description?.[language] ?? fallback?.description?.[language]}</p>
      <div className="rounded-xl border border-dashed border-border bg-muted/40 p-4">
        <p className="text-sm text-muted-foreground">{chatPlaceholder ?? localizedPlaceholder}</p>
      </div>
    </div>
  );
}

function StepRoute() {
  const { stepId } = useParams<{ stepId: string }>();
  if (!stepId) {
    const Fallback = STEP_COMPONENTS.project_selection;
    return <Fallback />;
  }
  const StepComponent = STEP_COMPONENTS[stepId as StepId];
  if (StepComponent) return <StepComponent />;
  return <Placeholder stepId={stepId} />;
}

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<ProjectSelectionView />} />
        <Route path="/step/:stepId" element={<StepRoute />} />
        <Route path="*" element={<ProjectSelectionView />} />
      </Route>
    </Routes>
  );
}
