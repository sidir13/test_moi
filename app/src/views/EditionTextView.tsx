import { useEffect } from "react";
import { MessageSquarePlus, PencilLine, Play, Sparkles, Volume2, Loader2 } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSelectedScenario, selectScenario, fetchProjectProfile } from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";

type TaggedParagraph = { partie_id: number; titre: string; taggedText: string };

type ContentChunk =
  | { type: "text"; value: string }
  | { type: "tag"; value: string; variant: "respiration" | "effet-sonore" | "voix" };

type InlineTagProps = {
  label: string;
  variant: "respiration" | "effet-sonore" | "voix";
};

type ParagraphBlockProps = {
  index: number;
  title: string;
  content: ContentChunk[];
};

type KeyWordChipProps = {
  label: string;
  variant: "respiration" | "effet-sonore";
};

function parseTaggedText(text: string, hideEffetSonore = false): ContentChunk[] {
  const chunks: ContentChunk[] = [];
  const regex = /(\ {[^}]+\}|\[[^\]]+\])/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      chunks.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }
    const tag = match[1];
    if (tag.startsWith("{")) {
      if (hideEffetSonore) {
        chunks.push({ type: "text", value: tag });
      } else {
        chunks.push({ type: "tag", value: tag.slice(1, -1), variant: "effet-sonore" });
      }
    } else {
      const inner = tag.slice(1, -1);
      if (/^(pause|silence|respiration)/i.test(inner)) {
        chunks.push({ type: "tag", value: inner, variant: "respiration" });
      } else {
        chunks.push({ type: "tag", value: inner, variant: "voix" });
      }
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    chunks.push({ type: "text", value: text.slice(lastIndex) });
  }
  return chunks;
}

function InlineTag({ label, variant }: InlineTagProps) {
  const className =
    variant === "respiration"
      ? "inline-flex items-center rounded-[4px] border border-[#623DC7] bg-[#E1D6FF] px-2 py-1 text-[12px] font-medium text-[#2F1E64]"
      : variant === "effet-sonore"
      ? "inline-flex items-center rounded-[4px] border border-[#C8009C] bg-[#FDEBF9] px-2 py-1 text-[12px] font-medium text-[#7D005F]"
      : "inline-flex items-center rounded-[4px] border border-[#64748B] bg-[#F1F5F9] px-2 py-1 text-[12px] font-medium text-[#334155]";
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
  const { sessionId, projectName } = useSessionStore();
  const queryClient = useQueryClient();

  const profileQuery = useQuery({
    queryKey: ["project-profile", projectName],
    queryFn: () => fetchProjectProfile(projectName!),
    enabled: Boolean(projectName),
  });

  const ttsProvider: "elevenlabs" | "qwen" =
    profileQuery.data?.tts_provider === "qwen" ? "qwen" : "elevenlabs";

  const selectionQuery = useQuery({
    queryKey: ["selected-scenario", sessionId],
    queryFn: () => fetchSelectedScenario(sessionId!),
    enabled: Boolean(sessionId),
  });

  const raw = selectionQuery.data as Record<string, unknown> | undefined;

  const taggedParagraphs: TaggedParagraph[] = (() => {
    if (!raw) return [];
    const taggedOutput = raw.taggedOutput as Record<string, unknown> | undefined;
    if (taggedOutput && Array.isArray(taggedOutput.parties) && taggedOutput.parties.length > 0) {
      return (taggedOutput.parties as Array<Record<string, unknown>>).map((p, i) => ({
        partie_id: (p.partie_id as number) ?? i + 1,
        titre: (p.titre as string) ?? `Partie ${i + 1}`,
        taggedText: (p.taggedText as string) ?? "",
      }));
    }
    const scenario = (raw.scenario as Record<string, unknown> | undefined) ?? raw;
    if (Array.isArray(scenario.parties)) {
      return (scenario.parties as Array<Record<string, unknown>>).map((p, i) => ({
        partie_id: i + 1,
        titre: (p.titre as string) ?? `Partie ${i + 1}`,
        taggedText: ((p.texte_narration ?? p.texte) as string) ?? "",
      }));
    }
    return [];
  })();

  const scenarioTitle = (() => {
    if (!raw) return "";
    const scenario = (raw.scenario as Record<string, unknown> | undefined) ?? raw;
    return (scenario.titre as string) ?? "";
  })();

  useEffect(() => {
    (window as Window & { __taggedParagraphs?: TaggedParagraph[] }).__taggedParagraphs = taggedParagraphs;
    return () => {
      (window as Window & { __taggedParagraphs?: TaggedParagraph[] }).__taggedParagraphs = undefined;
    };
  }, [taggedParagraphs]);

  useEffect(() => {
    (window as Window & { __ttsProvider?: string }).__ttsProvider = ttsProvider;
    return () => {
      (window as Window & { __ttsProvider?: string }).__ttsProvider = undefined;
    };
  }, [ttsProvider]);

  useEffect(() => {
    const handler = async (e: Event) => {
      const { paragraphs } = (e as CustomEvent<{ paragraphs: TaggedParagraph[] }>).detail;
      if (!sessionId || !raw) return;
      const updated: Record<string, unknown> = {
        ...raw,
        taggedOutput: {
          ...((raw.taggedOutput as Record<string, unknown>) ?? {}),
          parties: paragraphs,
        },
      };
      await selectScenario(sessionId, updated);
      queryClient.invalidateQueries({ queryKey: ["selected-scenario", sessionId] });
    };
    window.addEventListener("tagged-scenario-updated", handler);
    return () => window.removeEventListener("tagged-scenario-updated", handler);
  }, [sessionId, raw, queryClient]);

  if (!sessionId) {
    return <p className="p-6 text-sm text-muted-foreground">Demarrez une session.</p>;
  }

  if (selectionQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Chargement du scenario...
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1100px] rounded-[14px] border border-[#8EA4BD] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
      <div className="flex w-full items-center gap-6 rounded-t-[14px] border-b-[0.8px] border-[#E2E8F0] bg-[#F8FAFC] px-5 py-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="inline-flex items-center gap-2">
            <PencilLine className="h-4 w-4 text-[#45556C]" />
            <h2 className="text-[14px] font-medium leading-[14px] text-[#45556C]">Edition du scenario</h2>
          </div>
          <p className="text-[14px] font-normal leading-5 text-[#45556C]">
            Modifier et baliser le scenario pour generer un audio.
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-6 p-6">
        <article className="flex w-full flex-col gap-6 rounded-[18px] border border-[#8EA4BD] bg-white p-[25px] shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
          <div className="flex items-start justify-between gap-6">
            <div className="flex min-h-[109px] flex-1 flex-col gap-3">
              <h3 className="text-[18px] font-semibold leading-[18px] text-[#1E293B]">Scenario</h3>
              {scenarioTitle && (
                <p className="text-[22px] font-bold leading-[24px] text-[#0F172B]">{scenarioTitle}</p>
              )}
            </div>

            <div className="flex w-[245px] flex-col gap-[18px] rounded-[16px] border-t-[0.8px] border-[#E2E8F0] bg-[#F8FAFC] p-4">
              <div className="inline-flex items-center justify-between">
                <span className="text-[16px] font-semibold leading-[16px] text-[#0F172B]">Echantillon audio</span>
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
              <span>Demander a l&apos;agent IA</span>
            </button>
            {ttsProvider === "elevenlabs" && <KeyWordChip label="Effet Sonore" variant="effet-sonore" />}
            <KeyWordChip label="Respiration" variant="respiration" />
            <button type="button" className="inline-flex items-center gap-1 text-[14px] font-medium text-[#0F172B]">
              <MessageSquarePlus className="h-4 w-4" />
              <span>Ajouter un commentaire</span>
            </button>
          </div>

          <div className="flex w-full flex-col gap-8 rounded-[12px] border-t border-[#E2E8F0] bg-white p-[18px]">
            {taggedParagraphs.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun paragraphe a afficher.</p>
            ) : (
              taggedParagraphs.map((paragraph) => (
                <ParagraphBlock
                  key={paragraph.partie_id}
                  index={paragraph.partie_id}
                  title={paragraph.titre}
                  content={parseTaggedText(paragraph.taggedText, ttsProvider === "qwen")}
                />
              ))
            )}
          </div>
        </article>
      </div>
    </div>
  );
}

export function EditionTextView() {
  return (
    <div className="mx-auto w-full max-w-[1100px] p-6">
      <EditionScenario />
    </div>
  );
}
