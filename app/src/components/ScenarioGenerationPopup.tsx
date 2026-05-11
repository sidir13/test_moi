import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { fetchScenarioProgress } from "@/api/client";

type ScenarioGenerationPopupProps = {
  open: boolean;
  sessionId?: string | null;
  onClose: () => void;
  onComplete: () => void;
  onError?: (message: string) => void;
};

const STAGE_COUNT = 4;

export function ScenarioGenerationPopup({
  open,
  sessionId,
  onClose,
  onComplete,
  onError,
}: ScenarioGenerationPopupProps) {
  const completedRef = useRef(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      completedRef.current = false;
      setErrorMessage(null);
    }
  }, [open]);

  const progressQuery = useQuery({
    queryKey: ["scenario-progress", sessionId],
    queryFn: () => fetchScenarioProgress(sessionId!),
    enabled: open && Boolean(sessionId),
    refetchInterval: open ? 1500 : false,
  });

  const steps = progressQuery.data ?? [];

  const doneCount = useMemo(() => steps.filter((s) => s.status === "done").length, [steps]);
  const runningStep = useMemo(() => steps.find((s) => s.status === "running"), [steps]);
  const erroredStep = useMemo(() => steps.find((s) => s.status === "error"), [steps]);

  const segmentsTotal = Math.max(steps.length, STAGE_COUNT);
  const activeIndex = erroredStep
    ? steps.indexOf(erroredStep)
    : runningStep
      ? steps.indexOf(runningStep)
      : doneCount;

  const headline = erroredStep
    ? "Une erreur est survenue"
    : runningStep?.label ?? "Préparation des scénarios en cours";
  const subline = erroredStep
    ? erroredStep.message ?? "Génération interrompue."
    : runningStep?.message ?? "Cela prend généralement environ deux minutes.";

  useEffect(() => {
    if (!open) return;
    if (completedRef.current) return;
    if (erroredStep) {
      completedRef.current = true;
      const msg = erroredStep.message ?? "Erreur pendant la génération.";
      setErrorMessage(msg);
      onError?.(msg);
      return;
    }
    if (steps.length > 0 && steps.every((s) => s.status === "done")) {
      completedRef.current = true;
      onComplete();
    }
  }, [steps, erroredStep, open, onComplete, onError]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 px-4">
      <div className="relative flex h-[526px] w-[520px] flex-col justify-between rounded-[18px] border-t border-[#E2E8F0] bg-white p-10">
        <div className="mx-auto flex h-[224px] w-[438px] flex-col items-center gap-[25px]">
          <div className="flex h-[66.3px] w-[66.3px] items-center justify-center rounded-[12px] bg-[#007AFF] p-3">
            <Loader2 className="h-7 w-7 animate-spin text-white" />
          </div>
          <h3 className="text-center text-[20px] font-semibold leading-[20px] text-[#0F172B]">
            {headline}
          </h3>
          <p className="text-center text-[14px] font-normal leading-[22.75px] text-[#8EA4BD]">
            {subline}
          </p>
        </div>

        <div className="flex w-full flex-col gap-6">
          <div className="flex h-[80.5px] w-full flex-col items-center gap-[6px] rounded-lg border-t border-[#E2E8F0] bg-[#F4F4F4] px-[17px] pb-[1px] pt-[17px]">
            <p className="text-center text-[16px] font-semibold leading-[16px] text-[#8EA4BD]">Étape en cours</p>
            <p className="text-center text-[14px] font-semibold leading-[14px] text-[#0F172B]">
              {runningStep?.label ?? (erroredStep ? "Erreur" : "Démarrage…")}
            </p>
          </div>

          <div className="flex h-[9px] w-full gap-[7px]">
            {Array.from({ length: segmentsTotal }).map((_, index) => {
              const stepStatus = steps[index]?.status;
              const isCompleted = stepStatus === "done" || index < doneCount;
              const isCurrent = stepStatus === "running" || (!stepStatus && index === activeIndex);
              const isError = stepStatus === "error";
              return (
                <span
                  key={index}
                  className={`h-[9px] flex-1 rounded-[30px] transition-all duration-300 ${
                    isError
                      ? "bg-[#FF3B30]"
                      : isCompleted
                        ? "bg-[#007AFF]"
                        : isCurrent
                          ? "animate-pulse bg-[#007AFF]"
                          : "bg-[#E2E8F0]"
                  }`}
                />
              );
            })}
          </div>
        </div>

        <p className="mx-auto max-w-[434px] text-center text-[14px] font-normal leading-[14px] text-[#8EA4BD]">
          {errorMessage ?? "Veuillez ne pas fermer cette fenêtre. Vos scénarios seront prêts dans quelques instants…"}
        </p>

        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 inline-flex h-8 w-8 items-center justify-center rounded-full border border-[#E2E8F0] text-[#8EA4BD] transition-colors hover:bg-[#F8FAFC]"
          aria-label="Fermer la fenêtre de progression"
        >
          ×
        </button>
      </div>
    </div>
  );
}
