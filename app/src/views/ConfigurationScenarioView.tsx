import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Sparkles,
  Settings,
  ChevronDown,
  ChevronUp,
  Plus,
  Trash2,
  CircleAlert,
  AudioLines,
  RotateCcw,
  Check,
} from "lucide-react";
import {
  fetchProjectProfile,
  generateScenarios,
  fetchProjectAudio,
  saveAudioSelection,
  type ScenarioSpec,
} from "@/api/client";
import axios from "axios";
import { useSessionStore } from "@/hooks/useSessionStore";
import { ScenarioGenerationPopup } from "@/components/ScenarioGenerationPopup";
import { useQueryClient } from "@tanstack/react-query";

type AiProvider = "eleven_labs" | "qwen_local";

type ScenarioItem = {
  id: number;
  title: string;
  isOpen: boolean;
  aiProvider: AiProvider;
  prompt: string;
  targetAudience: string;
  narrativeTone: string;
  sourceMatch: number;
  durationSeconds: number;
};

export function ConfigurationScenarioView() {
  const navigate = useNavigate();
  const { projectName, lastProjectName, setProjectName, sessionId, setScenarioTarget } = useSessionStore();
  const queryClient = useQueryClient();
  const resolvedProjectName = projectName ?? lastProjectName;
  const [showAiDropdownId, setShowAiDropdownId] = useState<number | null>(null);
  const [showAudienceDropdownId, setShowAudienceDropdownId] = useState<number | null>(null);
  const [showToneDropdownId, setShowToneDropdownId] = useState<number | null>(null);
  const [showGenerationPopup, setShowGenerationPopup] = useState(false);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioItem[]>([
    {
      id: 1,
      title: "Scénario 1",
      isOpen: false,
      aiProvider: "eleven_labs",
      prompt: "",
      targetAudience: "Sélectionnez",
      narrativeTone: "Sélectionnez",
      sourceMatch: 70,
      durationSeconds: 90,
    },
  ]);
  const maxChars = 3000;
  const aiOptions = [
    {
      id: "eleven_labs" as const,
      label: "Eleven Labs",
      description: "Voix expressives, qualité élevée. Échantillon généré après le choix.",
    },
    {
      id: "qwen_local" as const,
      label: "Qwen local",
      description: "Plus de personnalisation, échantillon généré en fin d'artefact.",
    },
  ];
  const projectProfileQuery = useQuery({
    queryKey: ["configuration-project-profile", resolvedProjectName],
    queryFn: () => fetchProjectProfile(resolvedProjectName!),
    enabled: Boolean(resolvedProjectName),
  });
  const audienceOptions = projectProfileQuery.data?.preference_options?.audience_options ?? [];
  const toneOptions = projectProfileQuery.data?.preference_options?.tone_options ?? [];

  useEffect(() => {
    if (!projectName && lastProjectName) {
      setProjectName(lastProjectName);
    }
  }, [projectName, lastProjectName, setProjectName]);

  // Keep window.__scenarioPrompts in sync so ChatPanel can read prompt values
  useEffect(() => {
    (window as Window & { __scenarioPrompts?: string[] }).__scenarioPrompts = scenarios.map((s) => s.prompt);
    return () => {
      (window as Window & { __scenarioPrompts?: string[] }).__scenarioPrompts = undefined;
    };
  }, [scenarios]);

  // Listen for scenario-prompt-updated events dispatched by the chat agent tool
  useEffect(() => {
    const handler = (e: Event) => {
      const { scenario_index, action, content } = (e as CustomEvent<{ scenario_index: number; action: "replace" | "append"; content: string }>).detail;
      const idx = scenario_index ?? 0;
      setScenarios((prev) =>
        prev.map((s, i) =>
          i === idx
            ? { ...s, prompt: action === "replace" ? content : s.prompt + (s.prompt ? "\n" : "") + content }
            : s
        )
      );
    };
    window.addEventListener("scenario-prompt-updated", handler);
    return () => window.removeEventListener("scenario-prompt-updated", handler);
  }, []);

  useEffect(() => {
    if (!projectProfileQuery.data) return;
    const selectedAudience = projectProfileQuery.data.audience ?? audienceOptions[0] ?? "Sélectionnez";
    const selectedTone = projectProfileQuery.data.tone ?? toneOptions[0] ?? "Sélectionnez";
    setScenarios((prev) =>
      prev.map((scenario) => ({
        ...scenario,
        targetAudience: formatOptionLabel(selectedAudience),
        narrativeTone: formatOptionLabel(selectedTone),
      }))
    );
  }, [projectProfileQuery.data, audienceOptions, toneOptions]);

  const displayAudienceOptions =
    audienceOptions.length > 0 ? audienceOptions.map(formatOptionLabel) : ["Sélectionnez"];
  const displayToneOptions =
    toneOptions.length > 0 ? toneOptions.map(formatOptionLabel) : ["Sélectionnez"];

  const updateScenario = (id: number, patch: Partial<ScenarioItem>) => {
    setScenarios((prev) => prev.map((scenario) => (scenario.id === id ? { ...scenario, ...patch } : scenario)));
  };

  const handleAddScenario = () => {
    if (scenarios.length >= 3) return;
    const firstScenario = scenarios[0];
    const nextNumber = scenarios.length + 1;
    const newScenario: ScenarioItem = {
      ...firstScenario,
      id: Date.now(),
      title: `Scénario ${nextNumber}`,
      isOpen: false,
    };
    setScenarios((prev) => [...prev, newScenario]);
  };

  const handleDeleteScenario = (id: number) => {
    if (scenarios.length <= 1) return;
    setScenarios((prev) => prev.filter((scenario) => scenario.id !== id));
    if (showAiDropdownId === id) setShowAiDropdownId(null);
    if (showAudienceDropdownId === id) setShowAudienceDropdownId(null);
    if (showToneDropdownId === id) setShowToneDropdownId(null);
  };

  const reverseFormatLabel = (label: string, options: string[]) => {
    if (!label || label === "Sélectionnez") return undefined;
    const match = options.find((opt) => formatOptionLabel(opt) === label);
    return match ?? label.toLowerCase().replace(/\s+/g, "_");
  };

  const sourceUsageFromMatch = (value: number): "leger" | "modere" | "central" => {
    if (value <= 33) return "leger";
    if (value <= 66) return "modere";
    return "central";
  };

  const extractError = (err: unknown): string => {
    if (axios.isAxiosError(err)) {
      const detail = err.response?.data?.detail;
      if (typeof detail === "string" && detail.trim().length > 0) return detail;
      return err.message;
    }
    if (err instanceof Error) return err.message;
    return "Génération impossible.";
  };

  const handleGenerate = async () => {
    if (!sessionId || !resolvedProjectName) {
      setGenerationError("Aucune session active : sélectionnez d'abord un projet.");
      return;
    }
    const specs: ScenarioSpec[] = scenarios.map((s) => ({
      prompt: s.prompt.trim(),
      audience: reverseFormatLabel(s.targetAudience, audienceOptions),
      tone: reverseFormatLabel(s.narrativeTone, toneOptions),
      target_duration: s.durationSeconds,
      source_usage_level: sourceUsageFromMatch(s.sourceMatch),
      tts_provider: s.aiProvider === "qwen_local" ? "qwen" : "elevenlabs",
    }));
    const combinedPrompt = specs
      .map((s) => s.prompt)
      .filter((p) => Boolean(p))
      .join("\n\n");
    setGenerationError(null);
    setScenarioTarget(scenarios.length);
    setShowGenerationPopup(true);

    try {
      const projectAudio = await fetchProjectAudio(resolvedProjectName);
      if (!projectAudio || projectAudio.length === 0) {
        throw new Error(
          "Aucun fichier audio dans ce projet. Importez d'abord vos sources audio."
        );
      }
      const ttsProvider = specs[0]?.tts_provider ?? "elevenlabs";
      await saveAudioSelection(sessionId, {
        project_name: resolvedProjectName,
        voices: projectAudio.slice(0, 3),
        backgrounds: { ambient: null, punctual: [] },
        auto_backgrounds: false,
        tts_provider: ttsProvider,
        tts_voice_id: null,
      });

      await generateScenarios(
        sessionId,
        combinedPrompt,
        scenarios.length,
        "simple",
        undefined,
        specs
      );
      queryClient.invalidateQueries({ queryKey: ["scenarios", sessionId] });
    } catch (err) {
      setShowGenerationPopup(false);
      setGenerationError(extractError(err));
    }
  };

  return (
    <div className="mx-auto w-full max-w-[1100px] min-h-[806px] overflow-y-auto p-6">
      <section className="w-full overflow-hidden rounded-[14px] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
        <div className="flex items-center gap-6 border-b border-[#F4F4F4] bg-[#F8FAFC] px-5 py-4">
          <div className="flex min-w-0 flex-col gap-1">
            <div className="inline-flex items-center gap-2">
              <Settings className="h-5 w-5 text-[#0F172B]" />
              <h2 className="text-[20px] font-semibold leading-none text-[#0F172B]">Configuration des scénarios</h2>
            </div>
            <p className="text-[14px] font-medium leading-5 text-[#45556C]">
              Sélectionner plusieurs paramètres de générations pour vos scénarios.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-6 border-b border-[#F8FAFC] bg-white px-5 py-4">
          <div className="flex h-[38px] w-full items-center justify-end">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={!sessionId}
              className="inline-flex h-[38px] items-center gap-1 rounded-xl bg-[#007AFF] px-3 text-sm font-semibold text-white transition-colors hover:bg-[#006ae0] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Sparkles className="h-4 w-4" />
              <span>Générer</span>
            </button>
          </div>

          {scenarios.map((scenario) => {
            const selectedAi = aiOptions.find((o) => o.id === scenario.aiProvider) ?? aiOptions[0];
            return (
              <article key={scenario.id} className="flex flex-col gap-6 rounded-[18px] border border-[#8EA4BD] bg-white p-[25px] shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-[16px] font-medium leading-none text-[#0F172B]">{scenario.title}</h3>
                  <div className="inline-flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() => updateScenario(scenario.id, { isOpen: !scenario.isOpen })}
                      className="inline-flex h-[38px] items-center gap-2 rounded-xl border border-[#E2E8F0] bg-transparent px-3 text-sm font-medium text-[#45556C] transition-colors hover:bg-[#F8FAFC]"
                    >
                      <span>{scenario.isOpen ? "Voir moins" : "Voir plus"}</span>
                      {scenario.isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteScenario(scenario.id)}
                      disabled={scenarios.length <= 1}
                      className="inline-flex h-[38px] w-[38px] items-center justify-center rounded-xl border border-[#E2E8F0] bg-white text-[#FF3B30] transition-colors hover:bg-[#fff1f0] disabled:cursor-not-allowed disabled:opacity-40"
                      aria-label="Supprimer scénario"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <label className="inline-flex items-center gap-1 text-[14px] font-medium leading-5 text-[#0F172B]">
                    Prompt
                    <CircleAlert className="h-4 w-4" />
                  </label>
                  <div className="flex h-[92px] flex-col justify-between rounded-lg border border-[#E2E8F0] px-3 py-2">
                    <textarea
                      value={scenario.prompt}
                      onChange={(e) => updateScenario(scenario.id, { prompt: e.target.value.slice(0, maxChars) })}
                      placeholder="Ex. : Présente son histoire, son apprentissage dans une première partie, l'évolution de son métier à travers le temps dans une seconde..."
                      className="w-full resize-none bg-transparent text-[14px] font-normal leading-none text-[#45556C] outline-none placeholder:text-[#45556C]"
                      rows={2}
                    />
                    <p className="text-right text-[14px] font-normal leading-none text-[#45556C]">
                      {scenario.prompt.length}/{maxChars} caractères
                    </p>
                  </div>
                </div>

                {scenario.isOpen && (
                  <>
                    <div className="relative ml-auto inline-flex items-start">
                      <button
                        type="button"
                        onClick={() => setShowAiDropdownId((prev) => (prev === scenario.id ? null : scenario.id))}
                        className="inline-flex h-[38px] items-center gap-2 rounded-xl border border-[#007AFF] bg-[#EFF6FF] px-3 text-sm font-medium text-[#007AFF] transition-colors hover:bg-[#e6f2ff]"
                      >
                        <Sparkles className="h-4 w-4 text-[#007AFF]" />
                        <span>{selectedAi.label}</span>
                        <ChevronDown className="h-4 w-4 text-[#007AFF]" />
                      </button>

                      {showAiDropdownId === scenario.id && (
                        <div className="absolute right-0 top-[46px] z-30 w-[340px] -translate-x-4 overflow-hidden rounded-lg border border-[#E2E8F0] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
                          {aiOptions.map((option, idx) => (
                            <button
                              key={option.id}
                              type="button"
                              onClick={() => {
                                updateScenario(scenario.id, { aiProvider: option.id });
                                setShowAiDropdownId(null);
                              }}
                              className={`flex w-full items-start justify-between gap-[14px] px-5 py-5 text-left transition-colors hover:bg-[#F8FAFC] ${
                                idx < aiOptions.length - 1 ? "border-b border-[#E2E8F0]" : ""
                              }`}
                            >
                              <div className="flex flex-col gap-2">
                                <span className="text-[16px] font-semibold leading-none text-[#0F172B]">{option.label}</span>
                                <span className="text-[14px] font-normal leading-none text-[#45556C]">{option.description}</span>
                              </div>
                              {scenario.aiProvider === option.id ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-[#007AFF]" /> : null}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-6">
                      <div className="relative flex flex-col gap-2">
                        <label className="text-[14px] font-medium leading-5 text-[#0F172B]">Cible public</label>
                        <button
                          type="button"
                          onClick={() => {
                            setShowAudienceDropdownId((prev) => (prev === scenario.id ? null : scenario.id));
                            setShowToneDropdownId(null);
                          }}
                          className="inline-flex h-9 w-full items-center justify-between rounded-lg border border-[#E2E8F0] bg-[#F4F4F4] px-3 text-[14px] font-normal text-[#45556C]"
                        >
                          <span>{scenario.targetAudience}</span>
                          <ChevronDown className="h-4 w-4" />
                        </button>
                        {showAudienceDropdownId === scenario.id && (
                          <div className="absolute left-0 top-[68px] z-20 w-full overflow-hidden rounded-lg border border-[#E2E8F0] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
                            {displayAudienceOptions.map((option, index) => (
                              <button
                                key={`${option}-${index}`}
                                type="button"
                                onClick={() => {
                                  updateScenario(scenario.id, { targetAudience: option });
                                  setShowAudienceDropdownId(null);
                                }}
                                className={`w-full px-3 py-2 text-left text-[14px] text-[#45556C] transition-colors hover:bg-[#F8FAFC] ${
                                  index < displayAudienceOptions.length - 1 ? "border-b border-[#E2E8F0]" : ""
                                }`}
                              >
                                {option}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="relative flex flex-col gap-2">
                        <label className="text-[14px] font-medium leading-5 text-[#0F172B]">Ton narratif</label>
                        <button
                          type="button"
                          onClick={() => {
                            setShowToneDropdownId((prev) => (prev === scenario.id ? null : scenario.id));
                            setShowAudienceDropdownId(null);
                          }}
                          className="inline-flex h-9 w-full items-center justify-between rounded-lg border border-[#E2E8F0] bg-[#F4F4F4] px-3 text-[14px] font-normal text-[#45556C]"
                        >
                          <span>{scenario.narrativeTone}</span>
                          <ChevronDown className="h-4 w-4" />
                        </button>
                        {showToneDropdownId === scenario.id && (
                          <div className="absolute left-0 top-[68px] z-20 w-full overflow-hidden rounded-lg border border-[#E2E8F0] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
                            {displayToneOptions.map((option, index) => (
                              <button
                                key={`${option}-${index}`}
                                type="button"
                                onClick={() => {
                                  updateScenario(scenario.id, { narrativeTone: option });
                                  setShowToneDropdownId(null);
                                }}
                                className={`w-full px-3 py-2 text-left text-[14px] text-[#45556C] transition-colors hover:bg-[#F8FAFC] ${
                                  index < displayToneOptions.length - 1 ? "border-b border-[#E2E8F0]" : ""
                                }`}
                              >
                                {option}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {scenario.aiProvider !== "qwen_local" && (
                      <div className="flex flex-col gap-2">
                        <label className="text-[14px] font-medium leading-5 text-[#0F172B]">Choisir une voix</label>
                        <button
                          type="button"
                          className="inline-flex min-h-[66px] w-full items-center justify-between rounded-lg border border-[#E2E8F0] bg-[#F4F4F4] p-3"
                        >
                          <span className="inline-flex items-center gap-2 text-[14px] font-medium text-[#0F172B]">
                            <AudioLines className="h-4 w-4" />
                            Ben – Calm, Older, Masculine
                          </span>
                          <ChevronDown className="h-4 w-4 text-[#45556C]" />
                        </button>
                      </div>
                    )}

                    <div className="flex flex-col gap-2">
                      <div className="flex items-center justify-between text-[14px] font-medium leading-5 text-[#0F172B]">
                        <span>Correspondance à la source audio</span>
                        <button
                          type="button"
                          onClick={() => updateScenario(scenario.id, { sourceMatch: 70 })}
                          className="inline-flex items-center gap-1 text-[#45556C] hover:text-[#0F172B]"
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          <span>Réinitialiser</span>
                        </button>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-[14px] font-normal text-[#45556C]">Identique</span>
                        <input
                          type="range"
                          min={0}
                          max={100}
                          value={scenario.sourceMatch}
                          onChange={(e) => updateScenario(scenario.id, { sourceMatch: Number(e.target.value) })}
                          className="h-2 w-full accent-[#007AFF]"
                        />
                      </div>
                      <p className="text-[14px] font-normal leading-none text-[#45556C]">
                        Détermine l&apos;importance de la transcription dans le récit.
                      </p>
                    </div>

                    <div className="flex flex-col gap-2">
                      <div className="flex items-center justify-between text-[14px] font-medium leading-5 text-[#0F172B]">
                        <span>Durée audio (minutes)</span>
                        <span>{Math.floor(scenario.durationSeconds / 60)} minutes {scenario.durationSeconds % 60} s</span>
                      </div>
                      <input
                        type="range"
                        min={0}
                        max={600}
                        value={scenario.durationSeconds}
                        onChange={(e) => updateScenario(scenario.id, { durationSeconds: Number(e.target.value) })}
                        className="h-2 w-full accent-[#007AFF]"
                      />
                      <span className="text-[14px] font-normal leading-none text-[#45556C]">0:00</span>
                    </div>
                  </>
                )}
              </article>
            );
          })}

          <button
            type="button"
            onClick={handleAddScenario}
            disabled={scenarios.length >= 3}
            className="flex h-[218px] w-full cursor-pointer flex-col items-center justify-center gap-6 rounded-[18px] border border-dashed border-[#EFF6FF] bg-white p-[25px] transition-colors hover:bg-[#fafdff] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <span className="inline-flex h-[52px] w-[52px] items-center justify-center rounded-[12px] bg-[#007AFF] text-white">
              <Plus className="h-7 w-7" />
            </span>
            <div className="flex flex-col items-center gap-2">
              <p className="text-center text-[16px] font-semibold leading-none text-[#45556C]">Ajouter un scénario</p>
              <p className="text-center text-[12px] font-normal leading-none text-[#8EA4BD]">
                Vous pouvez générer jusqu&apos;à 3 scénarios.
              </p>
            </div>
          </button>
        </div>
      </section>

      {generationError && (
        <div className="mt-4 rounded-lg border border-[#FF3B30] bg-[#fff1f0] px-4 py-3 text-sm text-[#FF3B30]">
          {generationError}
        </div>
      )}

      <ScenarioGenerationPopup
        open={showGenerationPopup}
        sessionId={sessionId}
        onClose={() => setShowGenerationPopup(false)}
        onComplete={() => {
          setShowGenerationPopup(false);
          navigate("/step/choix_scenario");
        }}
        onError={(msg) => {
          setShowGenerationPopup(false);
          setGenerationError(msg);
        }}
      />
    </div>
  );
}

function formatOptionLabel(value: string) {
  if (!value || value === "Sélectionnez") return value || "Sélectionnez";
  return value
    .split("_")
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");
}
