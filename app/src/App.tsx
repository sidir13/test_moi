import { Component, useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, Outlet, Route, Routes, useLocation, useParams } from "react-router-dom";
import { Check, PencilLine, X } from "lucide-react";

import { fetchSteps, fetchStepConfig } from "./api/client";
import logoUrl from "@/assets/svg/LOGO.svg?url";
import logoutIconUrl from "@/assets/svg/logout.svg?url";
import profileIconUrl from "@/assets/svg/profile.svg?url";
import { StepNavigator } from "./components/StepNavigator";
// import { FlagToggle } from "./components/FlagToggle";
import { ChatPanel } from "./components/ChatPanel";
import { useSessionStore } from "./hooks/useSessionStore";
import { ProjectSelectionView } from "./views/ProjectSelectionView";
import { ProjectDetailsView } from "./views/ProjectDetailsView";
import { AudioSelectionView } from "./views/AudioSelectionView";
import { TranscriptionReviewView } from "./views/TranscriptionReviewView";
import { ScenarioReviewView } from "./views/ScenarioReviewView";
import { ScenarioEditView } from "./views/ScenarioEditView";
import { FinalValidationView } from "./views/FinalValidationView";
import { ConfigurationScenarioView } from "./views/ConfigurationScenarioView";

type StepId =
  | "project_selection"
  | "project_details"
  | "audio_sources"
  | "transcription_review"
  | "scenario_review"
  | "scenario_edit"
  | "final_validation"
  | "configuration_scenario";

const STEP_COMPONENTS: Record<StepId, React.ComponentType> = {
  project_selection: ProjectSelectionView,
  project_details: ProjectDetailsView,
  audio_sources: AudioSelectionView,
  transcription_review: TranscriptionReviewView,
  scenario_review: ScenarioReviewView,
  scenario_edit: ScenarioEditView,
  final_validation: FinalValidationView,
  configuration_scenario: ConfigurationScenarioView
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
  const { setSteps, currentStep, projectName } = useSessionStore();
  const location = useLocation();
  const isProjectDetailsPage = location.pathname === "/step/project_details";
  const isConfigurationScenarioPage = location.pathname === "/step/configuration_scenario";
  const showTopProjectBanner = isProjectDetailsPage || isConfigurationScenarioPage;
  const [showProjectDetailsBanner, setShowProjectDetailsBanner] = useState(true);
  const [isChatCollapsed, setIsChatCollapsed] = useState(false);
  const { data: stepsResponse } = useQuery({ queryKey: ["steps"], queryFn: fetchSteps });

  useEffect(() => {
    if (stepsResponse?.steps) {
      setSteps(stepsResponse.steps);
    }
  }, [stepsResponse, setSteps]);

  useEffect(() => {
    if (showTopProjectBanner) {
      setShowProjectDetailsBanner(true);
    }
  }, [showTopProjectBanner]);

  const isProjectSelectionPage =
    location.pathname === "/" || location.pathname === "/step/project_selection";

  const showChat =
    isConfigurationScenarioPage ||
    (Boolean(currentStep) &&
      !isProjectSelectionPage &&
      currentStep !== "project_selection" &&
      currentStep !== "final_validation");

  const showStepNavigator = !isProjectSelectionPage;
  const chatTopOffsetClass = showTopProjectBanner && showProjectDetailsBanner
    ? "top-[113px] h-[calc(100vh-113px)]"
    : "top-[64px] h-[calc(100vh-64px)]";
  const contentTopPaddingClass = showTopProjectBanner && showProjectDetailsBanner ? "pt-[49px]" : "";
  const contentRightPaddingClass = showChat ? (isChatCollapsed ? "pr-[68px]" : "pr-[258px]") : "";

  return (
    <div className="flex min-h-screen flex-col bg-muted">
      <div className="sticky top-0 z-50">
        <header className="flex items-center justify-between border-b border-border bg-background px-6 py-3 shadow-sm">
          <div className="flex min-w-0 items-center gap-3">
            <Link
              to="/"
              className="shrink-0 rounded-md outline-none ring-offset-2 focus-visible:ring-2 focus-visible:ring-ring"
              aria-label="Accueil — Mémoire des Territoires"
            >
              <img src={logoUrl} alt="" width={40} height={40} className="size-10 rounded-md" />
            </Link>
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold text-foreground leading-tight">Mémoire des Territoires</h1>
              <p className="text-xs font-normal text-muted-foreground leading-normal">Archivage et Artifacts</p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-0.5">
            {/* <FlagToggle /> */}
            <button
              type="button"
              className="inline-flex size-10 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
              aria-label="Déconnexion"
            >
              <img src={logoutIconUrl} alt="" width={20} height={20} className="size-5" />
            </button>
            <button
              type="button"
              className="inline-flex size-10 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background"
              aria-label="Profil"
            >
              <img src={profileIconUrl} alt="" width={22} height={22} className="size-[22px]" />
            </button>
          </div>
        </header>

        {showTopProjectBanner && showProjectDetailsBanner && (
          <div className="absolute left-0 right-0 top-full z-40 flex items-center justify-between gap-3 border-b border-border bg-background px-6 py-2.5">
            <div className="flex h-[29px] w-[288px] items-center gap-3 min-w-0">
              <h2 className="truncate text-[24px] font-semibold leading-[29px] text-foreground">
                {projectName ?? "Nouveau projet"}
              </h2>
              <PencilLine className="h-4 w-4 text-muted-foreground shrink-0" />
            </div>
            <div className="flex items-center gap-4 shrink-0">
              <div className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                <Check className="h-3.5 w-3.5 text-blue-500" />
                <span>Votre archive est enregistrée</span>
              </div>
              <button
                type="button"
                onClick={() => setShowProjectDetailsBanner(false)}
                className="inline-flex h-[33.6px] min-w-[80px] items-center justify-center gap-1 rounded-full border border-[#D0D5DD] bg-[#E2E8F0] px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-[#d6dee9]"
              >
                <X className="h-5 w-5 shrink-0  text-foreground" />
                <span>Fermer</span>
              </button>
            </div>
          </div>
        )}

        {showChat && (
          <aside
            className={`absolute right-0 ${chatTopOffsetClass} ${
              isChatCollapsed ? "w-[68px]" : "w-[258px]"
            } z-30 bg-white overflow-hidden flex flex-col transition-[width,top,height] duration-200 ease-out`}
          >
            <ChatPanel collapsed={isChatCollapsed} onToggleCollapsed={() => setIsChatCollapsed((v) => !v)} />
          </aside>
        )}
      </div>

      <div className={`flex flex-1 ${contentTopPaddingClass} ${contentRightPaddingClass}`}>
        {/* <StepNavigator /> hidden on project selection landing */} 
        {showStepNavigator ? (
          <aside className="w-64 shrink-0 border-r border-border bg-background overflow-y-auto p-4">
            <StepNavigator />
          </aside>
        ) : null}

        <main className="flex-1 p-6">
          <ErrorBoundary>
            <Outlet />
          </ErrorBoundary>
        </main>

      </div>

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
      <h2 className="text-xl font-semibold text-foreground">
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
