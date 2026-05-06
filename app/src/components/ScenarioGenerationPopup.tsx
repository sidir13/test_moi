import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

type ScenarioGenerationPopupProps = {
  open: boolean;
  onClose: () => void;
  onComplete: () => void;
};

export function ScenarioGenerationPopup({ open, onClose, onComplete }: ScenarioGenerationPopupProps) {
  const [activeSegment, setActiveSegment] = useState(0);

  useEffect(() => {
    if (!open) return;
    setActiveSegment(0);
    const intervalId = window.setInterval(() => {
      setActiveSegment((prev) => {
        if (prev >= 3) {
          window.clearInterval(intervalId);
          onComplete();
          return prev;
        }
        return prev + 1;
      });
    }, 850);

    return () => window.clearInterval(intervalId);
  }, [open, onComplete]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/25 px-4">
      <div className="relative flex h-[526px] w-[520px] flex-col justify-between rounded-[18px] border-t border-[#E2E8F0] bg-white p-10">
        <div className="mx-auto flex h-[224px] w-[438px] flex-col items-center gap-[25px]">
          <div className="flex h-[66.3px] w-[66.3px] items-center justify-center rounded-[12px] bg-[#007AFF] p-3">
            <Loader2 className="h-7 w-7 animate-spin text-white" />
          </div>
          <h3 className="text-center text-[20px] font-semibold leading-[20px] text-[#0F172B]">
            Préparation des scénarios en cours
          </h3>
          <p className="text-center text-[14px] font-normal leading-[22.75px] text-[#8EA4BD]">
            Cela prend généralement environ deux minutes.
          </p>
        </div>

        <div className="flex w-full flex-col gap-6">
          <div className="flex h-[80.5px] w-full flex-col items-center gap-[6px] rounded-lg border-t border-[#E2E8F0] bg-[#F4F4F4] px-[17px] pb-[1px] pt-[17px]">
            <p className="text-center text-[16px] font-semibold leading-[16px] text-[#8EA4BD]">Étape en cours</p>
            <p className="text-center text-[14px] font-semibold leading-[14px] text-[#0F172B]">
              Génération des scénarios en cours...
            </p>
          </div>

          <div className="flex h-[9px] w-full gap-[7px]">
            {Array.from({ length: 4 }).map((_, index) => {
              const isCurrent = activeSegment === index;
              const isCompleted = index < activeSegment;
              return (
                <span
                  key={index}
                  className={`h-[9px] flex-1 rounded-[30px] transition-all duration-300 ${
                    isCompleted
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
          Veuillez ne pas fermer cette fenêtre. Vos scénarios seront prêts dans quelques instants…
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
