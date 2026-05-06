import { CheckCircle2, Sparkles } from "lucide-react";

export function ChoixScenarioView() {
  return (
    <div className="w-full max-w-[870px] p-6">
      <section className="w-full rounded-[14px] bg-white p-6 shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
        <div className="mb-6 flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-[#007AFF]" />
          <h2 className="text-[24px] font-semibold leading-[29px] text-[#0F172B]">Choix scénario</h2>
        </div>

        <div className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-5">
          <div className="mb-2 inline-flex items-center gap-2 text-[#007AFF]">
            <CheckCircle2 className="h-4 w-4" />
            <span className="text-sm font-semibold">Scénarios générés</span>
          </div>
          <p className="text-[14px] text-[#45556C]">
            Cette page est prête. Tu peux maintenant afficher ici les scénarios générés pour permettre le choix.
          </p>
        </div>
      </section>
    </div>
  );
}
