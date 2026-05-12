import { ChevronRight, Loader2, PencilLine, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchProjectProfile,
  fetchScenarioAudio,
  fetchSelectedScenario,
  selectScenario,
  synthesizeScenarioAudio,
} from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";

type EditablePart = {
  titre: string;
  texte_narration: string;
  [key: string]: unknown;
};

type KeyWordChipProps = {
  label: string;
  variant: "respiration" | "effet-sonore";
};

function KeyWordChip({ label, variant }: KeyWordChipProps) {
  const className =
    variant === "respiration"
      ? "inline-flex h-6 items-center gap-1 rounded-[4px] border border-[#623DC7] bg-[#E1D6FF] px-2 py-1 text-[12px] font-medium text-[#2F1E64]"
      : "inline-flex h-6 items-center gap-1 rounded-[4px] border border-[#C8009C] bg-[#FDEBF9] px-2 py-1 text-[12px] font-medium text-[#7D005F]";
  return <span className={className}>{label}</span>;
}

export function EditionTextView() {
  const navigate = useNavigate();
  const { sessionId, projectName, lastProjectName, setCurrentStep } = useSessionStore();
  const resolvedProjectName = projectName ?? lastProjectName;
  const [parts, setParts] = useState<EditablePart[]>([]);
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);

  const selectionQuery = useQuery({
    queryKey: ["selected-scenario", sessionId],
    queryFn: () => fetchSelectedScenario(sessionId!),
    enabled: Boolean(sessionId),
  });

  const profileQuery = useQuery({
    queryKey: ["project-profile", resolvedProjectName],
    queryFn: () => fetchProjectProfile(resolvedProjectName!),
    enabled: Boolean(resolvedProjectName),
  });

  const audioQuery = useQuery({
    queryKey: ["scenario-audio", sessionId],
    queryFn: () => fetchScenarioAudio(sessionId!),
    enabled: Boolean(sessionId),
  });

  const isElevenLabs = profileQuery.data?.tts_provider === "elevenlabs";

  useEffect(() => {
    if (!selectionQuery.data) return;
    const raw = selectionQuery.data as Record<string, unknown>;
    const payload = (raw.scenario as Record<string, unknown> | undefined) ?? raw;
    const partiesRaw = Array.isArray(payload?.parties)
      ? (payload.parties as Array<Record<string, unknown>>)
      : [];
    setParts(
      partiesRaw.map((p) => ({
        ...p,
        titre: typeof p.titre === "string" ? p.titre : "",
        texte_narration: typeof p.texte_narration === "string" ? p.texte_narration : "",
      }))
    );
    setIsDirty(false);
  }, [selectionQuery.data]);

  const updatePart = (idx: number, patch: Partial<EditablePart>) => {
    setParts((prev) => prev.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
    setIsDirty(true);
  };

  const proceedToScenarioEdit = () => {
    setCurrentStep("scenario_edit");
    navigate("/step/scenario_edit");
  };

  const goToAudioEdition = async () => {
    if (!sessionId) return;
    setGenerateError(null);
    setIsSaving(true);

    try {
      // 1. Save edited text
      if (selectionQuery.data) {
        const raw = selectionQuery.data as Record<string, unknown>;
        const merged: Record<string, unknown> = { ...raw };
        if (merged.scenario && typeof merged.scenario === "object") {
          merged.scenario = { ...(merged.scenario as Record<string, unknown>), parties: parts };
        } else {
          merged.parties = parts;
        }
        await selectScenario(sessionId, merged);
      }

      // 2. Skip generation if audio is already done and text wasn't edited
      const audio = audioQuery.data;
      const needsAudio = isDirty || !audio?.path || audio?.status !== "done";
      if (!needsAudio) {
        proceedToScenarioEdit();
        return;
      }
    } finally {
      setIsSaving(false);
    }

    // 3. Show loading screen and generate
    setIsGenerating(true);
    try {
      await synthesizeScenarioAudio(sessionId);

      // 4. Poll until done or failed (max ~3 min)
      for (let i = 0; i < 90; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const result = await fetchScenarioAudio(sessionId);
        if (result?.status === "done") {
          proceedToScenarioEdit();
          return;
        }
        if (result?.status === "failed") {
          throw new Error(result.error ?? "Génération de l'audio échouée.");
        }
      }
      throw new Error("Délai de génération dépassé.");
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Erreur lors de la génération.");
    } finally {
      setIsGenerating(false);
    }
  };

  const raw = selectionQuery.data as Record<string, unknown> | undefined;
  const payload = (raw?.scenario as Record<string, unknown> | undefined) ?? raw;
  const scenarioLabel =
    (raw?.scenario_index != null ? `Scénario ${raw.scenario_index}` : null) ?? "Scénario";
  const scenarioTitle =
    (payload?.titre as string | undefined) ??
    (payload?.title as string | undefined) ??
    "";
  const axeNarratif = (payload?.axe_narratif as string | undefined) ?? "";

  if (isGenerating) {
    return (
      <div className="mx-auto flex w-full max-w-[1100px] flex-col items-center justify-center gap-6 p-6">
        <div className="w-full rounded-[14px] border border-[#8EA4BD] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)] flex flex-col items-center gap-6 py-20 px-8">
          <Loader2 className="h-12 w-12 animate-spin text-[#007AFF]" />
          <div className="flex flex-col items-center gap-2 text-center">
            <h2 className="text-[20px] font-semibold text-[#0F172B]">Génération de l'audio</h2>
            <p className="text-[14px] text-[#45556C]">
              Synthèse vocale en cours, veuillez patienter…
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-4 p-6">
      <div className="mx-auto w-full max-w-[1100px] rounded-[14px] border border-[#8EA4BD] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)]">

        {/* Header */}
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
          {selectionQuery.isLoading ? (
            <div className="flex items-center gap-2 text-[14px] text-[#45556C]">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
            </div>
          ) : (
            <article className="flex w-full flex-col gap-6 rounded-[18px] border border-[#8EA4BD] bg-white p-[25px] shadow-[0_2px_10px_rgba(0,0,0,0.10)]">

              {/* Scenario header */}
              <div className="flex min-h-[60px] flex-col gap-2">
                <h3 className="text-[18px] font-semibold leading-[18px] text-[#1E293B]">{scenarioLabel}</h3>
                {scenarioTitle && (
                  <p className="text-[22px] font-bold leading-[24px] text-[#0F172B]">{scenarioTitle}</p>
                )}
                {axeNarratif && (
                  <span className="inline-flex h-8 w-fit items-center justify-center rounded-[40px] border border-[#E2E8F0] bg-white px-4 py-1.5 text-[14px] font-semibold leading-[14px] text-[#45556C]">
                    {axeNarratif}
                  </span>
                )}
              </div>

              {/* AI + keyword chips */}
              <div className="flex flex-wrap items-center gap-3 rounded-[14px] border-[0.8px] border-[#5BA9FF] bg-[#EFF6FF] p-[10px]">
                <button
                  type="button"
                  className="inline-flex h-[38px] items-center gap-1 rounded-[12px] bg-[linear-gradient(135deg,#007AFF_0%,#8CC3FF_100%)] px-3 text-[14px] font-medium text-white"
                >
                  <Sparkles className="h-4 w-4" />
                  <span>Demander à l&apos;agent IA</span>
                </button>
                {isElevenLabs && (
                  <>
                    <KeyWordChip label="Effet Sonore" variant="effet-sonore" />
                    <KeyWordChip label="Respiration" variant="respiration" />
                  </>
                )}
              </div>

              {/* Editable parts */}
              <div className="flex w-full flex-col gap-8 rounded-[12px] border-t border-[#E2E8F0] bg-white p-[18px]">
                {parts.length === 0 && (
                  <p className="text-[14px] text-[#94a3b8]">Aucun contenu disponible.</p>
                )}
                {parts.map((part, idx) => (
                  <div key={idx} className="flex w-full flex-col gap-2">
                    <div className="inline-flex items-center gap-2">
                      <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#007AFF] text-[12px] font-semibold text-white">
                        {idx + 1}
                      </span>
                      <input
                        type="text"
                        value={part.titre}
                        onChange={(e) => updatePart(idx, { titre: e.target.value })}
                        placeholder="Titre de la partie"
                        className="flex-1 rounded-md border border-transparent bg-transparent px-1 text-[14px] font-semibold text-[#0F172B] outline-none transition-colors hover:border-[#E2E8F0] focus:border-[#007AFF]"
                      />
                    </div>
                    <textarea
                      value={part.texte_narration}
                      onChange={(e) => updatePart(idx, { texte_narration: e.target.value })}
                      placeholder="Texte de narration…"
                      rows={Math.max(3, Math.ceil((part.texte_narration?.length ?? 0) / 80))}
                      className="w-full resize-y rounded-md border border-transparent bg-transparent px-1 text-[14px] font-normal leading-6 text-[#334155] outline-none transition-colors hover:border-[#E2E8F0] focus:border-[#007AFF]"
                    />
                  </div>
                ))}
              </div>
            </article>
          )}
        </div>
      </div>

      {generateError && (
        <div className="flex w-full items-center justify-between gap-3 rounded-[12px] border border-[#FF3B30] bg-[#fff1f0] px-4 py-3 text-[13px] text-[#FF3B30]">
          <span>{generateError}</span>
          <button
            type="button"
            onClick={proceedToScenarioEdit}
            className="shrink-0 text-[13px] font-medium underline hover:no-underline"
          >
            Continuer sans audio
          </button>
        </div>
      )}

      <div className="flex w-full items-center justify-end">
        <button
          type="button"
          onClick={goToAudioEdition}
          disabled={isSaving}
          className="inline-flex h-[38px] items-center gap-1 rounded-[12px] bg-[#007AFF] px-4 py-2 text-[14px] font-medium leading-[14px] text-white transition-colors hover:bg-[#006ae0] disabled:opacity-50"
        >
          {isSaving ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <>
              <span>Suivant : Édition de l&apos;audio</span>
              <ChevronRight className="h-4 w-4" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
