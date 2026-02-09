import { useEffect } from "react";
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
import { ScenarioReviewView } from "./views/ScenarioReviewView";
import { ScenarioEditView } from "./views/ScenarioEditView";
import { FinalValidationView } from "./views/FinalValidationView";

const STEP_COMPONENTS: Record<string, JSX.Element> = {
  project_selection: <ProjectSelectionView />,
  project_details: <ProjectDetailsView />,
  audio_sources: <AudioSelectionView />,
  scenario_review: <ScenarioReviewView />,
  scenario_edit: <ScenarioEditView />,
  final_validation: <FinalValidationView />
};

function Layout() {
  const { setSteps, currentStep } = useSessionStore();
  const { data: stepsResponse } = useQuery({ queryKey: ["steps"], queryFn: fetchSteps });

  useEffect(() => {
    if (stepsResponse?.steps) {
      setSteps(stepsResponse.steps);
    }
  }, [stepsResponse, setSteps]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>Mémoire des Territoires</h1>
          <p>NotebookLM pour archives sonores historiques</p>
        </div>
        <FlagToggle />
      </header>
      <main>
        <aside>
          <StepNavigator />
        </aside>
        <section className="workspace">
          <Outlet />
        </section>
        {currentStep && currentStep !== "project_selection" && currentStep !== "final_validation" && (
          <aside className="chat-panel">
            <ChatPanel />
          </aside>
        )}
      </main>
      <footer className="app-footer">
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
  const localizedPlaceholder = data?.chat_placeholder?.[language] ?? fallback?.chat_placeholder?.[language];
  useEffect(() => {
    if (localizedPlaceholder) {
      setChatPlaceholder(localizedPlaceholder);
    }
  }, [localizedPlaceholder, setChatPlaceholder]);

  return (
    <div className="step-view">
      <h2>{data?.name?.[language] ?? fallback?.name?.[language] ?? stepId}</h2>
      <p>{data?.description?.[language] ?? fallback?.description?.[language]}</p>
      <div className="placeholder-card">
        <p>{chatPlaceholder || localizedPlaceholder}</p>
      </div>
    </div>
  );
}

function StepRoute() {
  const { stepId } = useParams();
  if (!stepId) return STEP_COMPONENTS.project_selection;
  return STEP_COMPONENTS[stepId] ?? <Placeholder stepId={stepId} />;
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
