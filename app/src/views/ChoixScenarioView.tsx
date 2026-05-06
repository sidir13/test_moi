import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Sparkles,
  ChevronDown,
  ChevronUp,
  Trash2,
  RotateCcw,
  Volume2,
  Play,
} from "lucide-react";
import { fetchProjectAudio } from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";

type ScenarioChoice = {
  id: number;
  label: string;
  title: string;
  tags: string[];
  duration: string;
};

export function ChoixScenarioView() {
  const navigate = useNavigate();
  const { projectName, lastProjectName, setCurrentStep } = useSessionStore();
  const resolvedProjectName = projectName ?? lastProjectName;
  const [openIds, setOpenIds] = useState<number[]>([1]);
  const projectAudioQuery = useQuery({
    queryKey: ["choix-scenario-project-audio", resolvedProjectName],
    queryFn: () => fetchProjectAudio(resolvedProjectName!),
    enabled: Boolean(resolvedProjectName),
  });
  const uploadedAudioName = projectAudioQuery.data?.[0] ?? "audio_uploadé.mp3";
  const scenarios: ScenarioChoice[] = [
    {
      id: 1,
      label: "Scénario 1",
      title: "Récit chronologique des événements",
      tags: ["Narratif", "Chronologique"],
      duration: "2:42",
    },
    {
      id: 2,
      label: "Scénario 2",
      title: "Voix locale et mémoire vivante",
      tags: ["Immersif", "Témoignages"],
      duration: "3:05",
    },
    {
      id: 3,
      label: "Scénario 3",
      title: "Regards croisés sur le territoire",
      tags: ["Comparatif", "Contextuel"],
      duration: "2:28",
    },
  ];

  const toggleOpen = (id: number) => {
    setOpenIds((prev) => (prev.includes(id) ? prev.filter((value) => value !== id) : [...prev, id]));
  };

  return (
    <div className="mx-auto w-full max-w-[1100px] p-6">
      <section className="w-full shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
        <div className="flex w-full items-center gap-6 rounded-t-[14px] border-b-[0.8px] border-[#E2E8F0] bg-[#F8FAFC] px-5 py-4">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            <div className="inline-flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-[#007AFF]" />
              <h2 className="text-[20px] font-semibold leading-[20px] text-[#0F172B]">Choix du scénario</h2>
            </div>
            <p className="text-[14px] font-medium leading-5 text-[#45556C]">
              Sélectionner le scénario que vous souhaitez transformer en artefact.
            </p>
          </div>
        </div>

        <div className="flex w-full flex-col gap-7 rounded-b-[14px] border-b-[0.8px] border-[#E2E8F0] bg-white px-5 py-5">
          {scenarios.map((scenario) => {
            const isOpen = openIds.includes(scenario.id);
            return (
              <article
                key={scenario.id}
                className="flex min-w-[392px] w-full flex-col gap-6 rounded-[18px] border border-[#B8C8D6] bg-white p-[25px]"
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-[20px] font-semibold leading-[20px] text-[#0F172B]">{scenario.label}</h3>
                  <div className="inline-flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => toggleOpen(scenario.id)}
                      className="inline-flex h-[38px] items-center gap-2 rounded-[12px] border border-[#E2E8F0] bg-white px-3 text-[14px] font-medium text-[#0F172B] transition-colors hover:bg-[#F8FAFC]"
                    >
                      <span>{isOpen ? "Voir moins" : "Voir plus"}</span>
                      {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                    <button
                      type="button"
                      className="inline-flex h-[38px] w-[38px] items-center justify-center rounded-[12px] border border-[#E2E8F0] bg-white text-[#FF3B30] transition-colors hover:bg-[#fff1f0]"
                      aria-label="Supprimer scénario"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="flex items-start justify-between gap-6">
                  <div className="flex min-h-[109px] flex-1 flex-col gap-3">
                    <h4 className="text-[24px] font-semibold leading-[24px] text-[#0F172B]">{scenario.title}</h4>
                    <div className="flex flex-wrap gap-2">
                      {scenario.tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex h-8 items-center justify-center rounded-[40px] border border-[#E2E8F0] bg-white px-4 py-1.5 text-[14px] font-semibold leading-[14px] text-[#45556C]"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex w-[245px] flex-col gap-[18px] rounded-[16px] border-t-[0.8px] border-[#E2E8F0] bg-[#F8FAFC] p-4">
                    <div className="flex flex-col gap-1">
                      <span className="text-[16px] font-semibold leading-[16px] text-[#0F172B]">Échantillon audio</span>
                      <span className="truncate text-[12px] font-medium leading-[14px] text-[#45556C]">
                        {uploadedAudioName}
                      </span>
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
                          <span>{scenario.duration}</span>
                        </div>
                      </div>
                      <Volume2 className="h-5 w-5 text-[#0F172B]" />
                    </div>
                  </div>
                </div>

                <div className="flex w-full items-center justify-end gap-2">
                  <button
                    type="button"
                    className="inline-flex h-[38px] items-center gap-2 rounded-[12px] border border-[#E2E8F0] bg-white px-3 py-2 text-[14px] font-medium leading-[14px] text-[#0F172B] transition-colors hover:bg-[#F8FAFC]"
                  >
                    <RotateCcw className="h-4 w-4" />
                    <span>Regénérer</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setCurrentStep("edition_text");
                      navigate("/step/edition_text");
                    }}
                    className="inline-flex h-[38px] items-center gap-1 rounded-[12px] bg-[#007AFF] px-3 py-2 text-[14px] font-medium leading-[14px] text-white transition-colors hover:bg-[#006ae0]"
                  >
                    <span>Sélectionner</span>
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
