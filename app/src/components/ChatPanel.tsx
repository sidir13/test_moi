import { type FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Send, Bot, User, Wrench, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getWsBaseUrl } from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";

type MessageRole = "user" | "assistant" | "system";

type ChatMessage = {
  role: MessageRole;
  content: string;
  subtype?: "tool_call" | "tool_result" | "error";
};

export function ChatPanel() {
  const { t } = useTranslation();
  const { chatPlaceholder, steps, currentStep, sessionId } = useSessionStore();
  const availableSkills = steps.find((s) => s.id === currentStep)?.skills ?? [];
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
          message?: string;
        };
        if (payload.type === "assistant_text") {
          setMessages((prev) => [...prev, { role: "assistant", content: payload.text ?? "" }]);
        } else if (payload.type === "tool_call") {
          setMessages((prev) => [
            ...prev,
            { role: "system", content: payload.tool ?? "", subtype: "tool_call" }
          ]);
        } else if (payload.type === "tool_result") {
          setMessages((prev) => [
            ...prev,
            { role: "system", content: payload.tool ?? "", subtype: "tool_result" }
          ]);
          if (payload.tool === "auto_select_audio" || payload.tool === "select_audio_manually") {
            window.dispatchEvent(new Event("audio-selection-updated"));
          }
        } else if (payload.type === "error") {
          setMessages((prev) => [
            ...prev,
            { role: "system", content: payload.message ?? "Erreur inconnue", subtype: "error" }
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
    ws.send(JSON.stringify({ text: message }));
    setInput("");
  };

  return (
    <div className={cn("flex flex-col h-full", !chatEnabled && "opacity-50 pointer-events-none")}>
      {availableSkills.length > 0 && (
        <div className="flex flex-wrap gap-1.5 p-3 border-b border-border">
          {availableSkills.map((skill) => (
            <Badge key={skill} variant="secondary" className="text-xs">
              {skill}
            </Badge>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-2 text-center p-4">
            <Bot className="h-8 w-8 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">{chatPlaceholder ?? "Posez votre question"}</p>
          </div>
        )}
        {messages.map((msg, idx) => (
          <MessageBubble key={idx} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-border p-3">
        {status && (
          <p className="text-xs text-destructive mb-2 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            {status}
          </p>
        )}
        <form onSubmit={send} className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              chatEnabled
                ? t("chat.placeholder", { defaultValue: "Posez votre question…" })
                : "Disponible après sélection du projet"
            }
            disabled={!chatEnabled}
            className="flex-1 rounded-full border border-input bg-background px-3 py-1.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!chatEnabled || !input.trim()}
            className="shrink-0 rounded-full"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "system") {
    const isToolCall = message.subtype === "tool_call";
    const isToolResult = message.subtype === "tool_result";
    const isError = message.subtype === "error";

    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-lg px-3 py-2 text-xs",
          isError && "bg-destructive-muted text-destructive",
          isToolCall && "bg-info-muted text-info-foreground",
          isToolResult && "bg-success-muted text-success",
          !isError && !isToolCall && !isToolResult && "bg-muted text-muted-foreground"
        )}
      >
        {isToolCall && <Wrench className="h-3 w-3 shrink-0" />}
        {isToolResult && <CheckCircle2 className="h-3 w-3 shrink-0" />}
        {isError && <AlertCircle className="h-3 w-3 shrink-0" />}
        <span>
          {isToolCall && `Outil utilisé : ${message.content}`}
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
        <div className="flex items-start gap-2 max-w-[85%]">
          <div className="rounded-2xl rounded-tr-sm bg-primary px-3 py-2 text-sm text-primary-foreground">
            {message.content}
          </div>
          <User className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-2 max-w-[90%]">
      <Bot className="mt-1 h-4 w-4 shrink-0 text-primary" />
      <div className="rounded-2xl rounded-tl-sm bg-muted px-3 py-2 text-sm">
        <MarkdownDisplay text={message.content} />
      </div>
    </div>
  );
}

function MarkdownDisplay({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1 leading-relaxed">
      {lines.map((line, idx) => {
        if (line.startsWith("### ")) return <h4 key={idx} className="font-semibold text-sm">{renderInline(line.slice(4))}</h4>;
        if (line.startsWith("## ")) return <h3 key={idx} className="font-semibold">{renderInline(line.slice(3))}</h3>;
        if (line.startsWith("# ")) return <h2 key={idx} className="font-bold">{renderInline(line.slice(2))}</h2>;
        if (line.startsWith("- ")) return <p key={idx} className="pl-3">• {renderInline(line.slice(2))}</p>;
        if (!line.trim()) return <br key={idx} />;
        return <p key={idx}>{renderInline(line)}</p>;
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
      return <code key={idx} className="rounded bg-background px-1 font-mono text-xs">{part.slice(1, -1)}</code>;
    return <span key={idx}>{part}</span>;
  });
}
