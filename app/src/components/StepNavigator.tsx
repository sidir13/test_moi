import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useSessionStore } from "../hooks/useSessionStore";

export function StepNavigator() {
  const { steps, currentStep, setCurrentStep, language } = useSessionStore();
  const navigate = useNavigate();

  const ordered = useMemo(() => steps.slice().sort((a, b) => {
    const ao = (a as any).order ?? 0;
    const bo = (b as any).order ?? 0;
    return ao - bo;
  }), [steps]);

  const currentIndex = ordered.findIndex((s) => s.id === currentStep);

  return (
    <nav className="step-navigator">
      {ordered.map((step, index) => {
        let status = "pending";
        if (step.id === currentStep) status = "current";
        if (index > -1 && currentIndex > -1 && index < currentIndex) {
          status = "done";
        }
        return (
          <button
            key={step.id}
            className={`step ${status}`}
            onClick={() => {
              setCurrentStep(step.id);
              navigate(step.id === ordered[0]?.id ? "/" : `/step/${step.id}`);
            }}
          >
            <span className="step-label">{step.name?.[language] ?? step.id}</span>
            <small>{step.description?.[language]}</small>
          </button>
        );
      })}
    </nav>
  );
}
