import { FormEvent, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { getWsBaseUrl } from "../api/client";
import { useSessionStore } from "../hooks/useSessionStore";

type ChatMessage = {
  role: "user" | "assistant" | "system";
  content: string;
};

export function ChatPanel() {
  const { t } = useTranslation();
  const { chatPlaceholder, steps, currentStep, sessionId } = useSessionStore();
  const availableSkills = steps.find((s) => s.id === currentStep)?.skills ?? [];
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const chatEnabled = Boolean(sessionId) && currentStep !== "project_selection";

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
        const payload = JSON.parse(event.data);
        if (payload.type === "assistant_text") {
          setMessages((prev) => [...prev, { role: "assistant", content: payload.text }]);
          return;
        }
        if (payload.type === "tool_call") {
          setMessages((prev) => [...prev, { role: "system", content: `🔧 Outil utilisé : ${payload.tool}` }]);
          return;
        }
        if (payload.type === "tool_result") {
          setMessages((prev) => [...prev, { role: "system", content: `✅ ${payload.tool} terminé` }]);
          if (payload.tool === "auto_select_audio" || payload.tool === "select_audio_manually") {
            window.dispatchEvent(new Event("audio-selection-updated"));
          }
          return;
        }
        if (payload.type === "error") {
          setStatus(payload.message);
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
    <div className={`chat-wrapper ${chatEnabled ? "" : "chat-disabled"}`}>
      <div className="skill-chips">
        {availableSkills.map((skill) => (
          <span key={skill} className="chip">
            {skill}
          </span>
        ))}
      </div>
      <div className="chat-messages">
        {messages.length === 0 && <p className="placeholder">{chatPlaceholder}</p>}
        {messages.map((msg, idx) => (
          <div key={idx} className={`bubble ${msg.role}`}>
            {msg.role === "assistant" ? <MarkdownDisplay text={msg.content} /> : <span>{msg.content}</span>}
          </div>
        ))}
      </div>
      <div className="chat-input">
        <form onSubmit={send} className="chat-form">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              chatEnabled
                ? t("chat.placeholder", { defaultValue: "Posez votre question" })
                : "Disponible après sélection du projet"
            }
            disabled={!chatEnabled}
          />
          <button type="submit" disabled={!chatEnabled}>
            {t("chat.send", { defaultValue: "Envoyer" })}
          </button>
        </form>
      </div>
      {status && <p className="status">{status}</p>}
    </div>
  );
}

function MarkdownDisplay({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="markdown">
      {lines.map((line, idx) => {
        if (line.startsWith("### ")) {
          return (
            <h4 key={idx}>
              {renderInline(line.replace("### ", ""))}
            </h4>
          );
        }
        if (line.startsWith("## ")) {
          return (
            <h3 key={idx}>
              {renderInline(line.replace("## ", ""))}
            </h3>
          );
        }
        if (line.startsWith("# ")) {
          return (
            <h2 key={idx}>
              {renderInline(line.replace("# ", ""))}
            </h2>
          );
        }
        if (line.startsWith("- ")) {
          return (
            <p key={idx} className="bullet">
              • {renderInline(line.replace("- ", ""))}
            </p>
          );
        }
        if (!line.trim()) {
          return <br key={idx} />;
        }
        return (
          <p key={idx}>
            {renderInline(line)}
          </p>
        );
      })}
    </div>
  );
}

function renderInline(content: string) {
  const parts = content.split(/(\*\*.+?\*\*|\*.+?\*|`.+?`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={idx}>
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return (
        <em key={idx}>
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={idx}>
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={idx}>{part}</span>;
  });
}
