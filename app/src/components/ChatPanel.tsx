import { type FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronRight, ChevronLeft, ArrowUp, Wrench, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { getWsBaseUrl } from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";
import { useQueryClient } from "@tanstack/react-query";
import aiLogoUrl from "@/assets/svg/ai-logo.svg?url";

type MessageRole = "user" | "assistant" | "system";

type ChatMessage = {
  role: MessageRole;
  content: string;
  subtype?: "tool_call" | "tool_result" | "error";
};

const MOCK_CHIPS = ["Scénario", "Contexte", "Scénario"];
const MOCK_SUGGESTION =
  "Je peux vous aider à rédiger le contexte de votre scénario. Dites moi quelle histoire vous souhaitez raconter\u00a0?";

type ChatPanelProps = {
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
};

export const ChatPanel = ({ collapsed = false, onToggleCollapsed }: ChatPanelProps) => {
  const { t } = useTranslation();
  const { chatPlaceholder, currentStep, sessionId, projectName } = useSessionStore();
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const chatEnabled = Boolean(sessionId) && currentStep !== "project_selection";

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!chatEnabled) {
      wsRef.current?.close();
      setMessages([]);
      return;
    }
    const wsUrl = `${getWsBaseUrl()}/ws/chat?session_id=${sessionId}`;
    const socket = new WebSocket(wsUrl);
    wsRef.current = socket;
    socket.onopen = () => setStatus(null);
    socket.onclose = () => setStatus("Chat déconnecté");
    socket.onerror = () => setStatus("Erreur de connexion");
    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data as string) as {
          type: string;
          text?: string;
          tool?: string;
          input?: Record<string, unknown>;
          result?: string;
          message?: string;
        };
        if (payload.type === "assistant_text") {
          setMessages((prev) => [...prev, { role: "assistant", content: payload.text ?? "" }]);
        } else if (payload.type === "tool_call") {
          setMessages((prev) => [
            ...prev,
            { role: "system", content: payload.tool ?? "", subtype: "tool_call" },
          ]);
        } else if (payload.type === "tool_result") {
          setMessages((prev) => [
            ...prev,
            { role: "system", content: payload.tool ?? "", subtype: "tool_result" },
          ]);
          if (payload.tool === "auto_select_audio" || payload.tool === "select_audio_manually") {
            window.dispatchEvent(new Event("audio-selection-updated"));
          }
          if (payload.tool === "select_voice") {
            try {
              const res = typeof payload.result === "string" ? JSON.parse(payload.result) : payload.result;
              if (res?.voice_id) {
                window.dispatchEvent(new CustomEvent("voice-selected", { detail: { voice_id: res.voice_id, voice_label: res.voice_label, reason: res.reason } }));
              }
            } catch { /* ignore parse errors */ }
          }
          if (payload.tool === "update_project_notes") {
            try {
              const res = typeof payload.result === "string" ? JSON.parse(payload.result) : payload.result;
              const updatedText: string | undefined = res?.project_notes;
              if (typeof updatedText === "string" && updatedText.length > 0) {
                window.dispatchEvent(new CustomEvent("project-notes-updated", {
                  detail: { text: updatedText }
                }));
              }
            } catch { /* ignore parse errors */ }
            // Fallback: invalidate project profile so React Query refetches fresh data
            if (projectName) {
              queryClient.invalidateQueries({ queryKey: ["project-profile", projectName] });
            }
          }
          if (payload.tool === "transcribe_audio" || payload.tool === "save_analysis_result") {
            window.dispatchEvent(new Event("transcription-updated"));
          }
        } else if (payload.type === "error") {
          setMessages((prev) => [
            ...prev,
            { role: "system", content: payload.message ?? "Erreur inconnue", subtype: "error" },
          ]);
        }
      } catch (err) {
        console.error("Invalid chat payload", err);
      }
    };
    return () => socket.close();
  }, [sessionId, chatEnabled]);

  const send = (evt: FormEvent) => {
    evt.preventDefault();
    if (!input.trim()) return;
    if (!chatEnabled) {
      setStatus("Le chatbot est indisponible à cette étape.");
      return;
    }
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setStatus("Chat indisponible");
      return;
    }
    const message = input.trim();
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    const currentNotes = (window as Window & { __projectNotes?: string }).__projectNotes;
    ws.send(JSON.stringify({ text: message, project_notes: currentNotes || undefined }));
    setInput("");
  };

  const isEmpty = messages.length === 0;
  const displaySuggestion = chatPlaceholder?.trim() ? chatPlaceholder : MOCK_SUGGESTION;

  if (collapsed) {
    return (
      <div className="relative flex h-full flex-col bg-white">
        <div className="px-3 pt-5">
          <button
            type="button"
            onClick={onToggleCollapsed}
            className="mx-auto flex h-8 w-8 items-center justify-center rounded-xl border border-[#D0D5DD] bg-[#F8FAFC] transition-colors hover:bg-[#eef2f7]"
            aria-label="Ouvrir le panneau"
          >
            <ChevronLeft className="h-4.5 w-4.5 text-muted-foreground" />
          </button>
        </div>

        <div className="flex-1" />

        <div className="pb-5">
          <img src={aiLogoUrl} alt="Agent AI" width={34} height={34} className="mx-auto rounded-full" />
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex flex-col h-full bg-white">
      {/* Collapse button */}
      <div className="absolute top-5 left-4 z-20">
        <button
          type="button"
          onClick={onToggleCollapsed}
          className="flex items-center justify-center w-7 h-7 rounded-md border border-border bg-white shadow-sm hover:bg-muted transition-colors"
          aria-label="Réduire le panneau"
        >
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      </div>

      {/* Centered hero content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <div className="mx-auto flex h-full w-full flex-col items-center justify-center px-3 text-center">
          <img src={aiLogoUrl} alt="Agent AI" width={52} height={52} className="rounded-full" />
          <p className="mt-2 text-[20px] font-semibold leading-tight text-foreground [font-family:Inter]">
            Agent AI
          </p>
          <p className="text-[12px] leading-normal text-muted-foreground [font-family:Inter]">
            You can ask anything
          </p>
        </div>
      </div>

      {/* Messages area */}
      <div className="px-3 pb-3 shrink-0">
        {isEmpty ? (
          <div className="mx-auto flex w-[234px] flex-col gap-[14px] rounded-[14px] border border-[#007AFF] bg-white p-3">
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-1">
                {MOCK_CHIPS.slice(0, 2).map((chip, i) => (
                  <span
                    key={i}
                    className="inline-flex h-8 items-center justify-center whitespace-nowrap rounded-[40px] border border-[#E2E8F0] bg-white px-4 py-1.5 text-[14px] font-normal leading-[14px] text-[#45556C]"
                  >
                    {chip}
                  </span>
                ))}
              </div>
              <div>
                <span className="inline-flex h-8 items-center justify-center whitespace-nowrap rounded-[40px] border border-[#E2E8F0] bg-white px-4 py-1.5 text-[14px] font-normal leading-[14px] text-[#45556C]">
                  {MOCK_CHIPS[2]}
                </span>
              </div>
            </div>
            <p className="w-full text-[14px] font-normal leading-[14px] text-[#007AFF]">{displaySuggestion}</p>
          </div>
        ) : (
          <div className="max-h-[180px] overflow-y-auto space-y-2.5">
            {messages.map((msg, idx) => (
              <MessageBubble key={idx} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="shrink-0 bg-[#F8FAFC] px-3 py-4 rounded-b-[14px] border-x-[0.8px] border-b-[0.8px] border-[#E2E8F0]">
        {status && (
          <p className="text-[10px] text-destructive mb-1.5 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            {status}
          </p>
        )}
        <form
          onSubmit={send}
          className="flex h-[37.6px] items-center justify-between gap-2 rounded-[32px] border-[0.8px] border-[#007AFF] bg-white px-3 py-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              chatEnabled
                ? t("chat.placeholder", { defaultValue: "Message" })
                : "Message"
            }
            disabled={!chatEnabled}
            className="flex-1 bg-transparent text-[14px] font-normal text-[#45556C] placeholder:text-[#45556C] outline-none disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={!chatEnabled || !input.trim()}
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Envoyer"
          >
            <ArrowUp className="h-4 w-4 text-[#007AFF]" />
          </button>
        </form>
      </div>
    </div>
  );
};

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "system") {
    const isToolCall = message.subtype === "tool_call";
    const isToolResult = message.subtype === "tool_result";
    const isError = message.subtype === "error";

    return (
      <div
        className={cn(
          "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10px]",
          isError && "bg-red-50 text-red-600",
          isToolCall && "bg-blue-50 text-blue-700",
          isToolResult && "bg-green-50 text-green-700",
          !isError && !isToolCall && !isToolResult && "bg-muted text-muted-foreground"
        )}
      >
        {isToolCall && <Wrench className="h-2.5 w-2.5 shrink-0" />}
        {isToolResult && <CheckCircle2 className="h-2.5 w-2.5 shrink-0" />}
        {isError && <AlertCircle className="h-2.5 w-2.5 shrink-0" />}
        <span>
          {isToolCall && `Outil\u00a0: ${message.content}`}
          {isToolResult && `${message.content} terminé`}
          {isError && message.content}
          {!isToolCall && !isToolResult && !isError && message.content}
        </span>
      </div>
    );
  }

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="rounded-2xl rounded-tr-sm bg-[#2563EB] px-3 py-1.5 text-[11px] text-white max-w-[85%]">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-1.5 max-w-[90%]">
      <img src={aiLogoUrl} alt="" width={18} height={18} className="rounded-full shrink-0 mt-0.5" />
      <div className="rounded-2xl rounded-tl-sm bg-muted px-3 py-1.5 text-[11px]">
        <MarkdownDisplay text={message.content} />
      </div>
    </div>
  );
}

function MarkdownDisplay({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-0.5 leading-relaxed">
      {lines.map((line, idx) => {
        if (line.startsWith("### ")) return <p key={idx} className="font-semibold text-[11px]">{renderInline(line.slice(4))}</p>;
        if (line.startsWith("## ")) return <p key={idx} className="font-semibold text-[11px]">{renderInline(line.slice(3))}</p>;
        if (line.startsWith("# ")) return <p key={idx} className="font-bold text-[11px]">{renderInline(line.slice(2))}</p>;
        if (line.startsWith("- ")) return <p key={idx} className="pl-2 text-[11px]">• {renderInline(line.slice(2))}</p>;
        if (!line.trim()) return <br key={idx} />;
        return <p key={idx} className="text-[11px]">{renderInline(line)}</p>;
      })}
    </div>
  );
}

function renderInline(content: string) {
  const parts = content.split(/(\*\*.+?\*\*|\*.+?\*|`.+?`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**"))
      return <strong key={idx}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("*") && part.endsWith("*"))
      return <em key={idx}>{part.slice(1, -1)}</em>;
    if (part.startsWith("`") && part.endsWith("`"))
      return <code key={idx} className="rounded bg-background px-1 font-mono text-[10px]">{part.slice(1, -1)}</code>;
    return <span key={idx}>{part}</span>;
  });
}
