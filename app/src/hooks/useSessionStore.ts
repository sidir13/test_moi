import { create } from "zustand";

export type Step = {
  id: string;
  order?: number;
  name: Record<string, string>;
  description: Record<string, string>;
  chat_placeholder: Record<string, string>;
  skills: string[];
};

const getInitialLastProject = () => {
  if (typeof window === "undefined") return undefined;
  return window.sessionStorage.getItem("lastProjectName") ?? undefined;
};

type SessionState = {
  sessionId?: string;
  projectName?: string;
  lastProjectName?: string;
  currentStep?: string;
  language: "fr" | "en";
  steps: Step[];
  chatPlaceholder?: string;
  scenarioTarget: number;
  progress: {
    audioReady: boolean;
    scenariosReady: boolean;
    scenarioChosen: boolean;
    scenarioEdited: boolean;
  };
  setProgress: (progress: SessionState["progress"]) => void;
  resetProgress: () => void;
  setLanguage: (lang: "fr" | "en") => void;
  setSteps: (steps: Step[]) => void;
  setCurrentStep: (stepId: string) => void;
  setChatPlaceholder: (placeholder: string) => void;
  setSessionId: (sessionId: string | undefined) => void;
  setProjectName: (name: string | undefined) => void;
  setLastProjectName: (name: string | undefined) => void;
  setScenarioTarget: (count: number) => void;
  updateProgress: (patch: Partial<SessionState["progress"]>) => void;
};

export const useSessionStore = create<SessionState>((set) => ({
  language: "fr",
  steps: [],
  scenarioTarget: 3,
  progress: {
    audioReady: false,
    scenariosReady: false,
    scenarioChosen: false,
    scenarioEdited: false
  },
  setProgress: (progress) =>
    set({
      progress: {
        audioReady: progress.audioReady,
        scenariosReady: progress.scenariosReady,
        scenarioChosen: progress.scenarioChosen,
        scenarioEdited: progress.scenarioEdited
      }
    }),
  resetProgress: () =>
    set({
      progress: {
        audioReady: false,
        scenariosReady: false,
        scenarioChosen: false,
        scenarioEdited: false
      }
    }),
  setLanguage: (language) =>
    set((state) => {
      const step = state.steps.find((s) => s.id === state.currentStep);
      const chatPlaceholder = step?.chat_placeholder?.[language] ?? state.chatPlaceholder;
      return { language, chatPlaceholder };
    }),
  setSteps: (steps) =>
    set((state) => {
      const first = steps[0];
      return {
        steps,
        currentStep: first?.id,
        chatPlaceholder: first?.chat_placeholder?.[state.language] ?? state.chatPlaceholder
      };
    }),
  setCurrentStep: (currentStep) =>
    set((state) => {
      const step = state.steps.find((s) => s.id === currentStep);
      const chatPlaceholder = step?.chat_placeholder?.[state.language] ?? state.chatPlaceholder;
      return { currentStep, chatPlaceholder };
    }),
  setChatPlaceholder: (chatPlaceholder) => set({ chatPlaceholder }),
  setSessionId: (sessionId) => set({ sessionId }),
  setProjectName: (projectName) => set({ projectName }),
  lastProjectName: getInitialLastProject(),
  setScenarioTarget: (scenarioTarget) => set({ scenarioTarget }),
  updateProgress: (patch) =>
    set((state) => ({
      progress: {
        ...state.progress,
        ...patch
      }
    })),
  setLastProjectName: (lastProjectName) => {
    if (typeof window !== "undefined") {
      if (lastProjectName) {
        window.sessionStorage.setItem("lastProjectName", lastProjectName);
      } else {
        window.sessionStorage.removeItem("lastProjectName");
      }
    }
    set({ lastProjectName });
  }
}));
