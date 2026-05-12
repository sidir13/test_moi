import { ChevronRight, PencilLine, Play, Sparkles, Volume2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useSessionStore } from "@/hooks/useSessionStore";

type InlineTagProps = {
  label: string;
  variant: "respiration" | "effet-sonore";
};

type ParagraphBlockProps = {
  index: number;
  title: string;
  content: Array<{ type: "text"; value: string } | { type: "tag"; value: string; variant: InlineTagProps["variant"] }>;
};

type KeyWordChipProps = {
  label: string;
  variant: "respiration" | "effet-sonore";
};

function InlineTag({ label, variant }: InlineTagProps) {
  const className =
    variant === "respiration"
      ? "inline-flex items-center rounded-[4px] border border-[#623DC7] bg-[#E1D6FF] px-2 py-1 text-[12px] font-medium text-[#2F1E64]"
      : "inline-flex items-center rounded-[4px] border border-[#C8009C] bg-[#FDEBF9] px-2 py-1 text-[12px] font-medium text-[#7D005F]";
  return <span className={className}>{label}</span>;
}

function KeyWordChip({ label, variant }: KeyWordChipProps) {
  const className =
    variant === "respiration"
      ? "inline-flex h-6 items-center gap-1 rounded-[4px] border border-[#623DC7] bg-[#E1D6FF] px-2 py-1 text-[12px] font-medium text-[#2F1E64]"
      : "inline-flex h-6 items-center gap-1 rounded-[4px] border border-[#C8009C] bg-[#FDEBF9] px-2 py-1 text-[12px] font-medium text-[#7D005F]";
  return <span className={className}>{label}</span>;
}

function ParagraphBlock({ index, title, content }: ParagraphBlockProps) {
  return (
    <div className="flex w-full flex-col gap-2">
      <div className="inline-flex items-center gap-2">
        <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[#007AFF] text-[12px] font-semibold text-white">
          {index}
        </span>
        <p className="text-[14px] font-semibold leading-[14px] text-[#0F172B]">[ {title} ]</p>
      </div>
      <p className="text-[14px] font-normal leading-6 text-[#334155]">
        {content.map((chunk, idx) =>
          chunk.type === "text" ? (
            <span key={idx}>{chunk.value}</span>
          ) : (
            <span key={idx} className="mx-1">
              <InlineTag label={chunk.value} variant={chunk.variant} />
            </span>
          )
        )}
      </p>
    </div>
  );
}

export function EditionScenario() {
  const paragraphs: ParagraphBlockProps[] = [
    {
      index: 1,
      title: "Le contexte historique",
      content: [
        { type: "text", value: "Au début du XXe siècle, les quais s’animent dès l’aube. " },
        { type: "tag", value: "Respiration 1.5s", variant: "respiration" },
        { type: "text", value: " Les dockers se préparent à une journée décisive pendant que les tensions sociales montent." },
      ],
    },
    {
      index: 2,
      title: "Le basculement",
      content: [
        { type: "text", value: "Lorsque l’annonce tombe, la foule réagit immédiatement. " },
        { type: "tag", value: "Effet sonore - foule", variant: "effet-sonore" },
        { type: "text", value: " Les voix se mêlent et la colère devient un mouvement collectif." },
      ],
    },
    {
      index: 3,
      title: "La résolution",
      content: [
        { type: "text", value: "Dans les jours suivants, une solidarité nouvelle s’installe. " },
        { type: "tag", value: "Respiration 2s", variant: "respiration" },
        { type: "text", value: " Le récit se termine sur une note d’espoir et de transmission." },
      ],
    },
  ];

  return (
    <div className="mx-auto w-full max-w-[1100px] rounded-[14px] border border-[#8EA4BD] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
      <div className="flex w-full items-center gap-6 rounded-t-[14px] border-b-[0.8px] border-[#E2E8F0] bg-[#F8FAFC] px-5 py-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="inline-flex items-center gap-2">
            <PencilLine className="h-4 w-4 text-[#45556C]" />
            <h2 className="text-[14px] font-medium leading-[14px] text-[#45556C]">Édition du scénario</h2>
          </div>
          <p className="text-[14px] font-normal leading-5 text-[#45556C]">
            Modifier et baliser le scénario pour générer un audio.
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-6 p-6">
        <article className="flex w-full flex-col gap-6 rounded-[18px] border border-[#8EA4BD] bg-white p-[25px] shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
          <div className="flex items-start justify-between gap-6">
            <div className="flex min-h-[109px] flex-1 flex-col gap-3">
              <h3 className="text-[18px] font-semibold leading-[18px] text-[#1E293B]">Scénario 1</h3>
              <p className="text-[22px] font-bold leading-[24px] text-[#0F172B]">Récit chronologique des événements</p>
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex h-8 items-center justify-center rounded-[40px] border border-[#E2E8F0] bg-white px-4 py-1.5 text-[14px] font-semibold leading-[14px] text-[#45556C]">
                  Narratif
                </span>
                <span className="inline-flex h-8 items-center justify-center rounded-[40px] border border-[#E2E8F0] bg-white px-4 py-1.5 text-[14px] font-semibold leading-[14px] text-[#45556C]">
                  Chronologique
                </span>
              </div>
            </div>

            <div className="flex w-[245px] flex-col gap-[18px] rounded-[16px] border-t-[0.8px] border-[#E2E8F0] bg-[#F8FAFC] p-4">
              <div className="inline-flex items-center justify-between">
                <span className="text-[16px] font-semibold leading-[16px] text-[#0F172B]">Échantillon audio</span>
                <Volume2 className="h-4 w-4 text-[#45556C]" />
              </div>
              <div className="inline-flex items-center gap-3">
                <button
                  type="button"
                  className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[#E2E8F0] bg-white text-[#0F172B]"
                  aria-label="Lecture"
                >
                  <Play className="h-4 w-4 fill-[#0F172B]" />
                </button>
                <div className="flex-1">
                  <div className="h-2 w-full rounded-[30px] bg-[#E2E8F0]">
                    <div className="h-2 w-[42%] rounded-[30px] bg-[#0F172B]" />
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[12px] font-semibold leading-[12px] text-[#45556C]">
                    <span>0:00</span>
                    <span>4:05</span>
                  </div>
                </div>
                <Volume2 className="h-5 w-5 text-[#0F172B]" />
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 rounded-[14px] border-[0.8px] border-[#5BA9FF] bg-[#EFF6FF] p-[10px]">
            <button
              type="button"
              className="inline-flex h-[38px] items-center gap-1 rounded-[12px] bg-[linear-gradient(135deg,#007AFF_0%,#8CC3FF_100%)] px-3 text-[14px] font-medium text-white"
            >
              <Sparkles className="h-4 w-4" />
              <span>Demander à l&apos;agent IA</span>
            </button>
            <KeyWordChip label="Effet Sonore" variant="effet-sonore" />
            <KeyWordChip label="Respiration" variant="respiration" />
          </div>

          <div className="flex w-full flex-col gap-8 rounded-[12px] border-t border-[#E2E8F0] bg-white p-[18px]">
            {paragraphs.map((paragraph) => (
              <ParagraphBlock key={paragraph.index} {...paragraph} />
            ))}
          </div>
        </article>
      </div>
    </div>
  );
}

export function EditionTextView() {
  const navigate = useNavigate();
  const { setCurrentStep } = useSessionStore();

  const goToAudioEdition = () => {
    setCurrentStep("scenario_edit");
    navigate("/step/scenario_edit");
  };

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-4 p-6">
      <EditionScenario />
      <div className="flex w-full items-center justify-end">
        <button
          type="button"
          onClick={goToAudioEdition}
          className="inline-flex h-[38px] items-center gap-1 rounded-[12px] bg-[#007AFF] px-4 py-2 text-[14px] font-medium leading-[14px] text-white transition-colors hover:bg-[#006ae0]"
        >
          <span>Suivant : Édition de l&apos;audio</span>
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
