import { type ReactNode, useEffect, useMemo, useState } from "react";
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
  Loader2,
} from "lucide-react";
import { fetchProjectAudio, fetchScenarios, selectScenario } from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";

type SentenceSource = { sentence: string; sources: string[] };
type ScenarioPart = {
  titre: string;
  texte_narration: string;
  sentence_sources: SentenceSource[];
};
type ScenarioChoice = {
  id: number;
  label: string;
  title: string;
  tags: string[];
  duration: string;
  parties: ScenarioPart[];
  aiPercent: number;
  hasSourcing: boolean;
  raw: Record<string, unknown>;
};

const formatDuration = (seconds: unknown): string => {
  const value = typeof seconds === "number" ? seconds : Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return "—";
  const m = Math.floor(value / 60);
  const s = Math.floor(value % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
};

const tagsForScenario = (raw: Record<string, unknown>): string[] => {
  const payload = (raw.scenario as Record<string, unknown> | undefined) ?? raw;
  const out = new Set<string>();
  const angle = (payload?.axe_narratif ?? raw.axe_narratif) as string | undefined;
  if (angle && typeof angle === "string") out.add(angle.replace(/_/g, " "));
  const themes = ((payload as Record<string, unknown>)?.themes ??
    (raw.scenario_config as Record<string, unknown> | undefined)?.historical_context) as
    | Record<string, unknown>
    | undefined;
  const primary = themes?.primary;
  if (Array.isArray(primary)) {
    primary.slice(0, 2).forEach((t) => typeof t === "string" && out.add(t));
  }
  const tagsField = (payload as Record<string, unknown>)?.tags;
  if (Array.isArray(tagsField)) {
    tagsField.slice(0, 2).forEach((t) => typeof t === "string" && out.add(t));
  }
  return Array.from(out).slice(0, 3);
};

const renderTextWithSourcing = (text: string, sentences: SentenceSource[]) => {
  const sourced = sentences.filter((s) => s.sources.length > 0 && s.sentence.length > 0);
  if (!text || sourced.length === 0) {
    return <span>{text}</span>;
  }
  const matches: { start: number; end: number; sources: string[] }[] = [];
  for (const item of sourced) {
    const pos = text.indexOf(item.sentence);
    if (pos >= 0) {
      matches.push({ start: pos, end: pos + item.sentence.length, sources: item.sources });
    }
  }
  if (matches.length === 0) return <span>{text}</span>;
  matches.sort((a, b) => a.start - b.start);
  const merged: typeof matches = [];
  for (const m of matches) {
    const last = merged[merged.length - 1];
    if (last && m.start < last.end) {
      last.end = Math.max(last.end, m.end);
      last.sources = Array.from(new Set([...last.sources, ...m.sources]));
    } else {
      merged.push({ ...m });
    }
  }
  const out: ReactNode[] = [];
  let cursor = 0;
  merged.forEach((m, i) => {
    if (cursor < m.start) out.push(<span key={`p-${i}`}>{text.slice(cursor, m.start)}</span>);
    out.push(
      <span
        key={`h-${i}`}
        title={m.sources.join(", ")}
        className="rounded bg-[#DBEAFE] px-0.5 text-[#1D4ED8]"
      >
        {text.slice(m.start, m.end)}
      </span>
    );
    cursor = m.end;
  });
  if (cursor < text.length) out.push(<span key="tail">{text.slice(cursor)}</span>);
  return <>{out}</>;
};

export function ChoixScenarioView() {
  const navigate = useNavigate();
  const { projectName, lastProjectName, setCurrentStep, sessionId, updateProgress } = useSessionStore();
  const resolvedProjectName = projectName ?? lastProjectName;
  const [openIds, setOpenIds] = useState<number[]>([1]);
  const [activeTab, setActiveTab] = useState<Record<number, "generation" | "sourcing">>({});
  const [selectingId, setSelectingId] = useState<number | null>(null);
  const [selectionError, setSelectionError] = useState<string | null>(null);

  const setTab = (id: number, tab: "generation" | "sourcing") => {
    setActiveTab((prev) => ({ ...prev, [id]: tab }));
  };

  const projectAudioQuery = useQuery({
    queryKey: ["choix-scenario-project-audio", resolvedProjectName],
    queryFn: () => fetchProjectAudio(resolvedProjectName!),
    enabled: Boolean(resolvedProjectName),
  });
  const scenariosQuery = useQuery({
    queryKey: ["scenarios", sessionId],
    queryFn: () => fetchScenarios(sessionId!),
    enabled: Boolean(sessionId),
  });

  const uploadedAudioName = projectAudioQuery.data?.[0] ?? "audio_uploadé.mp3";

  const scenarios = useMemo<ScenarioChoice[]>(() => {
    const data = scenariosQuery.data ?? [];
    return data.map((entry, idx) => {
      const raw = (entry ?? {}) as Record<string, unknown>;
      const payload = (raw.scenario as Record<string, unknown> | undefined) ?? raw;
      const title =
        (payload?.titre as string | undefined) ||
        (payload?.title as string | undefined) ||
        (raw.titre as string | undefined) ||
        `Scénario ${idx + 1}`;
      const duration = formatDuration(
        (payload?.duree_estimee as unknown) ?? (payload?.duration as unknown) ?? (raw?.duree as unknown)
      );

      const partiesRaw = Array.isArray(payload?.parties) ? (payload.parties as unknown[]) : [];
      const parties: ScenarioPart[] = partiesRaw
        .map((p, partIdx) => {
          if (!p || typeof p !== "object") return null;
          const part = p as Record<string, unknown>;
          const sentenceSourcesRaw = Array.isArray(part.sentence_sources)
            ? (part.sentence_sources as unknown[])
            : [];
          const sentence_sources: SentenceSource[] = sentenceSourcesRaw
            .map((it) => {
              if (!it || typeof it !== "object") return null;
              const obj = it as Record<string, unknown>;
              if (typeof obj.sentence !== "string") return null;
              const sourcesArr = Array.isArray(obj.sources) ? obj.sources : [];
              return {
                sentence: obj.sentence.trim(),
                sources: sourcesArr
                  .filter((s): s is string => typeof s === "string")
                  .map((s) => s.trim())
                  .filter(Boolean),
              };
            })
            .filter((x): x is SentenceSource => x !== null && x.sentence.length > 0);
          return {
            titre: typeof part.titre === "string" ? part.titre : `Partie ${partIdx + 1}`,
            texte_narration: typeof part.texte_narration === "string" ? part.texte_narration : "",
            sentence_sources,
          };
        })
        .filter((x): x is ScenarioPart => x !== null);

      let totalChars = 0;
      let sourcedChars = 0;
      for (const part of parties) {
        totalChars += part.texte_narration.length;
        for (const s of part.sentence_sources) {
          if (s.sources.length > 0) sourcedChars += s.sentence.length;
        }
      }
      const aiPercent =
        totalChars > 0
          ? Math.max(0, Math.min(100, Math.round(100 - (sourcedChars / totalChars) * 100)))
          : 100;
      const hasSourcing = parties.some((p) => p.sentence_sources.length > 0);

      return {
        id: (raw.scenario_index as number | undefined) ?? idx + 1,
        label: `Scénario ${(raw.scenario_index as number | undefined) ?? idx + 1}`,
        title,
        tags: tagsForScenario(raw),
        duration,
        parties,
        aiPercent,
        hasSourcing,
        raw,
      };
    });
  }, [scenariosQuery.data]);

  useEffect(() => {
    if (scenarios.length > 0) {
      updateProgress({ scenariosReady: true });
    }
  }, [scenarios, updateProgress]);

  const toggleOpen = (id: number) => {
    setOpenIds((prev) => (prev.includes(id) ? prev.filter((value) => value !== id) : [...prev, id]));
  };

  const handleSelect = async (scenario: ScenarioChoice) => {
    if (!sessionId) {
      setSelectionError("Session manquante.");
      return;
    }
    setSelectingId(scenario.id);
    setSelectionError(null);
    try {
      const merged: Record<string, unknown> = { ...scenario.raw };
      const innerSource =
        (merged.scenario as Record<string, unknown> | undefined) ?? merged;
      const innerClone: Record<string, unknown> = { ...innerSource, parties: scenario.parties };
      if ("scenario" in merged) {
        merged.scenario = innerClone;
      } else {
        merged.parties = scenario.parties;
      }
      await selectScenario(sessionId, merged);
      updateProgress({ scenarioChosen: true });
      setCurrentStep("edition_text");
      navigate("/step/edition_text");
    } catch (err) {
      setSelectionError(err instanceof Error ? err.message : "Sélection impossible.");
    } finally {
      setSelectingId(null);
    }
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
          {scenariosQuery.isLoading && (
            <div className="flex items-center gap-2 text-[14px] text-[#45556C]">
              <Loader2 className="h-4 w-4 animate-spin" />
              Chargement des scénarios…
            </div>
          )}
          {!scenariosQuery.isLoading && scenarios.length === 0 && (
            <p className="text-[14px] text-[#45556C]">
              Aucun scénario disponible. Lancez la génération depuis l'étape précédente.
            </p>
          )}
          {selectionError && (
            <div className="rounded-lg border border-[#FF3B30] bg-[#fff1f0] px-4 py-3 text-sm text-[#FF3B30]">
              {selectionError}
            </div>
          )}
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

                {isOpen && scenario.parties.length > 0 && (() => {
                  const tab = activeTab[scenario.id] ?? "generation";
                  const sourcingDisabled = !scenario.hasSourcing;
                  return (
                    <div className="flex w-full flex-col gap-4 rounded-[16px] border border-[#E2E8F0] bg-white p-4">
                      <div className="flex items-center justify-between gap-3">
                        <h5 className="text-[16px] font-semibold text-[#0F172B]">Texte de scénario</h5>
                        <div className="flex items-center gap-2">
                          {tab === "sourcing" && (
                            <span className="inline-flex h-7 items-center gap-1 rounded-full bg-[#EFF6FF] px-3 text-[12px] font-semibold text-[#1D4ED8]">
                              Texte inspiré à {100 - scenario.aiPercent}% de la source
                            </span>
                          )}
                          <div className="inline-flex overflow-hidden rounded-[10px] border border-[#E2E8F0]">
                            <button
                              type="button"
                              onClick={() => setTab(scenario.id, "generation")}
                              className={`px-3 py-1.5 text-[13px] font-medium transition-colors ${
                                tab === "generation"
                                  ? "bg-[#0F172B] text-white"
                                  : "bg-white text-[#45556C] hover:bg-[#F8FAFC]"
                              }`}
                            >
                              Génération
                            </button>
                            <button
                              type="button"
                              disabled={sourcingDisabled}
                              onClick={() => !sourcingDisabled && setTab(scenario.id, "sourcing")}
                              className={`px-3 py-1.5 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                                tab === "sourcing"
                                  ? "bg-[#0F172B] text-white"
                                  : "bg-white text-[#45556C] hover:bg-[#F8FAFC]"
                              }`}
                              title={sourcingDisabled ? "Aucune source identifiée pour ce scénario" : undefined}
                            >
                              Sourcing
                            </button>
                          </div>
                        </div>
                      </div>

                      <div className="flex max-h-[420px] flex-col gap-4 overflow-y-auto pr-1 text-[14px] leading-[22px] text-[#0F172B]">
                        {scenario.parties.map((part, i) => (
                          <div key={i} className="flex flex-col gap-1.5">
                            {part.titre && (
                              <p className="text-[15px] font-semibold text-[#0F172B]">{part.titre}</p>
                            )}
                            {part.texte_narration && (
                              <p className="whitespace-pre-line text-[14px] text-[#45556C]">
                                {tab === "sourcing"
                                  ? renderTextWithSourcing(part.texte_narration, part.sentence_sources)
                                  : part.texte_narration}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}

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
                    onClick={() => handleSelect(scenario)}
                    disabled={selectingId !== null}
                    className="inline-flex h-[38px] items-center gap-1 rounded-[12px] bg-[#007AFF] px-3 py-2 text-[14px] font-medium leading-[14px] text-white transition-colors hover:bg-[#006ae0] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {selectingId === scenario.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <span>Sélectionner</span>
                    )}
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
