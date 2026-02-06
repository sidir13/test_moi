import { create } from "zustand";

export type Step = {
  id: string;
  order?: number;
  name: Record<string, string>;
  description: Record<string, string>;
  chat_placeholder: Record<string, string>;
  skills: string[];
};

type SessionState = {
  sessionId?: string;
  projectName?: string;
  currentStep?: string;
  language: "fr" | "en";
  steps: Step[];
  chatPlaceholder?: string;
  setLanguage: (lang: "fr" | "en") => void;
  setSteps: (steps: Step[]) => void;
  setCurrentStep: (stepId: string) => void;
  setChatPlaceholder: (placeholder: string) => void;
};

export const useSessionStore = create<SessionState>((set) => ({
  language: "fr",
  steps: [],
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
  setChatPlaceholder: (chatPlaceholder) => set({ chatPlaceholder })
}));
