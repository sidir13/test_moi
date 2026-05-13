import { ChevronRight, Loader2, MessageSquarePlus, PencilLine, Play, Sparkles, Volume2 } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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
  dragText?: string;
};

function parseTaggedText(text: string, hideEffetSonore = false): ContentChunk[] {
  const chunks: ContentChunk[] = [];
  const regex = /( \{[^}]+\}|\[[^\]]+\])/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      chunks.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }
    const tag = match[1];
    if (tag.startsWith("{") || tag.startsWith(" {")) {
      if (hideEffetSonore) {
        chunks.push({ type: "text", value: tag });
      } else {
        chunks.push({ type: "tag", value: tag.replace(/^ ?\{|\}$/g, ""), variant: "effet-sonore" });
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

function ParagraphBlock({ index, title, content }: ParagraphBlockProps) {
  return (
    <div className="flex w-full flex-col gap-2">
      <div className="inline-flex items-center gap-2">
        <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#007AFF] text-[12px] font-semibold text-white">
          {index}
        </span>
        <span className="text-[14px] font-semibold text-[#0F172B]">{title}</span>
      </div>
      <p className="text-[14px] font-normal leading-6 text-[#334155]">
        {content.map((chunk, i) =>
          chunk.type === "text" ? (
            <span key={i}>{chunk.value}</span>
          ) : (
            <InlineTag key={i} label={chunk.value} variant={chunk.variant} />
          )
        )}
      </p>
    </div>
  );
}

function KeyWordChip({ label, variant, dragText }: KeyWordChipProps) {
  const baseClass =
    variant === "respiration"
      ? "inline-flex h-6 items-center gap-1 rounded-[4px] border border-[#623DC7] bg-[#E1D6FF] px-2 py-1 text-[12px] font-medium text-[#2F1E64]"
      : "inline-flex h-6 items-center gap-1 rounded-[4px] border border-[#C8009C] bg-[#FDEBF9] px-2 py-1 text-[12px] font-medium text-[#7D005F]";
  const className = dragText ? `${baseClass} cursor-grab active:cursor-grabbing select-none` : baseClass;
  return (
    <span
      className={className}
      draggable={Boolean(dragText)}
      onDragStart={dragText ? (e) => {
        e.dataTransfer.setData("text/plain", dragText);
        e.dataTransfer.effectAllowed = "copy";
        // Use the chip itself as drag image so the ghost looks like the colored chip
        const el = e.currentTarget;
        const rect = el.getBoundingClientRect();
        e.dataTransfer.setDragImage(el, e.clientX - rect.left, e.clientY - rect.top);
      } : undefined}
    >
      {label}
    </span>
  );
}

// ─── Rich-text helpers for TaggedTextarea ────────────────────────────────────

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Convert tagged plain text (with [pause Xs] / {son.wav}) to HTML with inline chip spans. */
function valueToHTML(text: string, hideEffetSonore = false): string {
  if (!text) return "";
  const chunks = parseTaggedText(text, false);
  return chunks
    .map((chunk) => {
      if (chunk.type === "text") return escapeHtml(chunk.value);
      if (hideEffetSonore && chunk.variant === "effet-sonore")
        return escapeHtml(` {${chunk.value}}`);

      // Only render as chip if it's a genuine production tag (short, no archive markers).
      // Archive references like [ARCHIVE : « ... »] must stay as plain editable text.
      const isGenuineTag =
        chunk.variant === "effet-sonore" ||
        chunk.variant === "respiration" ||
        (chunk.variant === "voix" &&
          !chunk.value.includes(":") &&
          !chunk.value.includes("«") &&
          !chunk.value.includes("»") &&
          chunk.value.length < 60);

      if (!isGenuineTag) {
        return escapeHtml(`[${chunk.value}]`);
      }

      const chipClass =
        chunk.variant === "respiration"
          ? "inline-flex items-center rounded-[4px] border border-[#623DC7] bg-[#E1D6FF] px-2 py-1 text-[12px] font-medium text-[#2F1E64]"
          : chunk.variant === "effet-sonore"
          ? "inline-flex items-center rounded-[4px] border border-[#C8009C] bg-[#FDEBF9] px-2 py-1 text-[12px] font-medium text-[#7D005F]"
          : "inline-flex items-center rounded-[4px] border border-[#64748B] bg-[#F1F5F9] px-2 py-1 text-[12px] font-medium text-[#334155]";
      // data-tag stores the raw tag text for round-trip serialization
      const rawTag = chunk.variant === "effet-sonore" ? ` {${chunk.value}}` : `[${chunk.value}]`;
      // Display friendly label instead of raw syntax
      const displayLabel = chunk.variant === "respiration" ? "Respiration" : chunk.variant === "effet-sonore" ? "Effet Sonore" : chunk.value;
      return `<span contenteditable="false" data-tag="${escapeHtml(rawTag)}" class="${chipClass}">${escapeHtml(displayLabel)}</span>`;
    })
    .join("");
}

/** Serialize a contenteditable div back to tagged plain text. */
function divToText(div: HTMLElement): string {
  let result = "";
  function traverse(node: Node): void {
    if (node.nodeType === Node.TEXT_NODE) {
      result += node.textContent ?? "";
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      const el = node as HTMLElement;
      if (el.dataset.tag !== undefined) {
        result += el.dataset.tag;
      } else if (el.tagName === "BR") {
        result += "\n";
      } else {
        const isBlock = el.tagName === "DIV" || el.tagName === "P";
        if (isBlock && result.length > 0 && !result.endsWith("\n")) result += "\n";
        el.childNodes.forEach(traverse);
      }
    }
  }
  div.childNodes.forEach(traverse);
  return result;
}

type TaggedTextareaProps = {
  value: string;
  onChange: (text: string) => void;
  hideEffetSonore: boolean;
  placeholder?: string;
};

/**
 * Contenteditable div that renders tagged text with inline colored chips.
 * caretRangeFromPoint works on div elements (unlike <textarea>), so drag-and-drop
 * inserts at the exact cursor position and the dropped element is a real HTML chip.
 */
function TaggedTextarea({ value, onChange, hideEffetSonore, placeholder }: TaggedTextareaProps) {
  const ref = useRef<HTMLDivElement>(null);
  // Track what is currently in the DOM to distinguish external vs internal updates
  const internalRef = useRef<string | null>(null);

  useLayoutEffect(() => {
    if (!ref.current) return;
    if (value !== internalRef.current) {
      ref.current.innerHTML = valueToHTML(value, hideEffetSonore);
      internalRef.current = value;
    }
  }, [value, hideEffetSonore]);

  return (
    <div
      ref={ref}
      contentEditable
      suppressContentEditableWarning
      data-placeholder={placeholder}
      onInput={(e) => {
        const text = divToText(e.currentTarget as HTMLDivElement);
        internalRef.current = text;
        onChange(text);
      }}
      onKeyDown={(e) => {
        // Prevent Chrome from wrapping new lines in <div> blocks
        if (e.key === "Enter") {
          e.preventDefault();
          document.execCommand("insertText", false, "\n");
        }
      }}
      onPaste={(e) => {
        // Strip rich text on paste
        e.preventDefault();
        const text = e.clipboardData.getData("text/plain");
        document.execCommand("insertText", false, text);
      }}
      onDragOver={(e) => {
        if (!e.dataTransfer.types.includes("text/plain")) return;
        e.preventDefault();
      }}
      onDrop={(e) => {
        e.preventDefault();
        const rawDrag = e.dataTransfer.getData("text/plain");
        if (!rawDrag) return;
        const trimmed = rawDrag.trim();

        // Exact drop position — works correctly on contenteditable divs
        const doc = document as Document & {
          caretRangeFromPoint?: (x: number, y: number) => Range | null;
          caretPositionFromPoint?: (x: number, y: number) => { offsetNode: Node; offset: number } | null;
        };
        let range: Range | null = null;
        if (doc.caretRangeFromPoint) {
          range = doc.caretRangeFromPoint(e.clientX, e.clientY); // Chrome / Safari
        } else if (doc.caretPositionFromPoint) {
          const pos = doc.caretPositionFromPoint(e.clientX, e.clientY); // Firefox
          if (pos) { range = document.createRange(); range.setStart(pos.offsetNode, pos.offset); range.collapse(true); }
        }
        if (!range) return;

        const sel = window.getSelection();
        sel?.removeAllRanges();
        sel?.addRange(range);

        const createChip = (dataTag: string, label: string, chipClass: string) => {
          const span = document.createElement("span");
          span.setAttribute("contenteditable", "false");
          span.dataset.tag = dataTag;
          span.className = chipClass;
          span.textContent = label;
          return span;
        };

        if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
          // Respiration-style tag: leading space is a word separator, not part of tag
          const inner = trimmed.slice(1, -1);
          const chipClass = /^(pause|silence|respiration)/i.test(inner)
            ? "inline-flex items-center rounded-[4px] border border-[#623DC7] bg-[#E1D6FF] px-2 py-1 text-[12px] font-medium text-[#2F1E64]"
            : "inline-flex items-center rounded-[4px] border border-[#64748B] bg-[#F1F5F9] px-2 py-1 text-[12px] font-medium text-[#334155]";
          const chipLabel = /^(pause|silence|respiration)/i.test(inner) ? "Respiration" : inner;
          if (rawDrag.startsWith(" ")) {
            const space = document.createTextNode(" ");
            range.insertNode(space);
            range.setStartAfter(space);
          }
          const chip = createChip(trimmed, chipLabel, chipClass);
          range.insertNode(chip);
          range.setStartAfter(chip);
        } else if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
          // Effet-sonore: leading space IS part of the tag syntax
          const chip = createChip(
            rawDrag, // " {son.wav}" — space included
            "Effet Sonore",
            "inline-flex items-center rounded-[4px] border border-[#C8009C] bg-[#FDEBF9] px-2 py-1 text-[12px] font-medium text-[#7D005F]",
          );
          range.insertNode(chip);
          range.setStartAfter(chip);
        } else {
          const node = document.createTextNode(rawDrag);
          range.insertNode(node);
          range.setStartAfter(node);
        }

        range.collapse(true);
        sel?.removeAllRanges();
        sel?.addRange(range);

        const text = divToText(ref.current!);
        internalRef.current = text;
        onChange(text);
      }}
      className="min-h-[72px] w-full whitespace-pre-wrap break-words rounded-md border border-transparent bg-transparent px-1 text-[14px] font-normal leading-6 text-[#334155] outline-none transition-colors hover:border-[#E2E8F0] focus:border-[#007AFF] empty:before:content-[attr(data-placeholder)] empty:before:text-slate-400 empty:before:pointer-events-none"
    />
  );
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

  const queryClient = useQueryClient();

  // Sync parts → window.__taggedParagraphs so ChatPanel can send them to the LLM
  // Also reads taggedOutput.parties[].taggedText as fallback (where Agent 3 stores data)
  useEffect(() => {
    const raw = selectionQuery.data as Record<string, unknown> | undefined;
    const taggedOutput = raw?.taggedOutput as Record<string, unknown> | undefined;
    const taggedParties = Array.isArray(taggedOutput?.parties) ? (taggedOutput!.parties as Array<Record<string, unknown>>) : [];

    const paragraphs: TaggedParagraph[] = parts.map((p, i) => {
      const tagged = taggedParties[i];
      const taggedText = (p.texte_narration && p.texte_narration.length > 0)
        ? p.texte_narration
        : ((tagged?.taggedText as string) ?? "");
      return { partie_id: i + 1, titre: p.titre, taggedText };
    });
    (window as Window & { __taggedParagraphs?: TaggedParagraph[] }).__taggedParagraphs = paragraphs;
    return () => {
      (window as Window & { __taggedParagraphs?: TaggedParagraph[] }).__taggedParagraphs = undefined;
    };
  }, [parts, selectionQuery.data]);

  // Listen for LLM edits via update_tagged_scenario tool
  useEffect(() => {
    const handler = async (e: Event) => {
      const { paragraphs } = (e as CustomEvent<{ paragraphs: TaggedParagraph[] }>).detail;
      if (!Array.isArray(paragraphs) || paragraphs.length === 0) return;
      // Update local parts state immediately (source of truth for the UI)
      setParts(
        paragraphs.map((p) => ({
          titre: p.titre,
          texte_narration: p.taggedText,
        }))
      );
      setIsDirty(true);
      // Persist to backend without triggering a refetch (would overwrite parts)
      if (!sessionId) return;
      const raw = (selectionQuery.data ?? {}) as Record<string, unknown>;
      const updatedParties = paragraphs.map((p) => ({ titre: p.titre, texte_narration: p.taggedText }));
      const merged: Record<string, unknown> = { ...raw };
      if (merged.scenario && typeof merged.scenario === "object") {
        merged.scenario = { ...(merged.scenario as Record<string, unknown>), parties: updatedParties };
      } else {
        merged.parties = updatedParties;
      }
      await selectScenario(sessionId, merged);
    };
    window.addEventListener("tagged-scenario-updated", handler);
    return () => window.removeEventListener("tagged-scenario-updated", handler);
  }, [sessionId, selectionQuery.data]);

  // Auto-save to backend 1.5s after last change so refresh doesn't lose edits
  useEffect(() => {
    if (!isDirty || !sessionId || !selectionQuery.data) return;
    const timer = setTimeout(async () => {
      const raw = selectionQuery.data as Record<string, unknown>;
      const merged: Record<string, unknown> = { ...raw };
      if (merged.scenario && typeof merged.scenario === "object") {
        merged.scenario = { ...(merged.scenario as Record<string, unknown>), parties: parts };
      } else {
        merged.parties = parts;
      }
      await selectScenario(sessionId, merged);
    }, 1500);
    return () => clearTimeout(timer);
  }, [parts, isDirty, sessionId, selectionQuery.data]);

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

      const audio = audioQuery.data;
      const needsAudio = isDirty || !audio?.path || audio?.status !== "done";
      if (!needsAudio) {
        proceedToScenarioEdit();
        return;
      }
    } finally {
      setIsSaving(false);
    }

    setIsGenerating(true);
    try {
      await synthesizeScenarioAudio(sessionId);

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
            <h2 className="text-[20px] font-semibold text-[#0F172B]">Génération de l&apos;audio</h2>
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

              <div className="flex flex-wrap items-center gap-3 rounded-[14px] border-[0.8px] border-[#5BA9FF] bg-[#EFF6FF] p-[10px]">
                <button
                  type="button"
                  className="inline-flex h-[38px] items-center gap-1 rounded-[12px] bg-[linear-gradient(135deg,#007AFF_0%,#8CC3FF_100%)] px-3 text-[14px] font-medium text-white"
                >
                  <Sparkles className="h-4 w-4" />
                  <span>Demander à l&apos;agent IA</span>
                </button>
                {isElevenLabs && <KeyWordChip label="Effet Sonore" variant="effet-sonore" dragText=" {Effet sonore}" />}
                <KeyWordChip label="Respiration" variant="respiration" dragText=" [Respiration]" />
              </div>

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
                    <TaggedTextarea
                      value={part.texte_narration}
                      onChange={(text) => updatePart(idx, { texte_narration: text })}
                      hideEffetSonore={!isElevenLabs}
                      placeholder="Texte de narration…"
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
