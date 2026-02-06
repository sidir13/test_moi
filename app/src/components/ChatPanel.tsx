import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useSessionStore } from "../hooks/useSessionStore";

export function ChatPanel() {
  const { t } = useTranslation();
  const { chatPlaceholder, steps, currentStep } = useSessionStore();
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");

  const send = () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { role: "user", content: input }]);
    setInput("");
  };

  const availableSkills = steps.find((s) => s.id === currentStep)?.skills ?? [];

  return (
    <div className="chat-wrapper">
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
            {msg.content}
          </div>
        ))}
      </div>
      <div className="chat-input">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("chat.placeholder", { defaultValue: "Posez votre question" })}
        />
        <button onClick={send}>{t("chat.send", { defaultValue: "Envoyer" })}</button>
      </div>
    </div>
  );
}
