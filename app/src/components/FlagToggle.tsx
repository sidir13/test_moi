import { useTranslation } from "react-i18next";

import { useSessionStore } from "../hooks/useSessionStore";

const flags: Record<string, string> = {
  fr: "🇫🇷",
  en: "🇬🇧"
};

export function FlagToggle() {
  const { i18n } = useTranslation();
  const { setLanguage } = useSessionStore();

  const switchLanguage = (lang: "fr" | "en") => {
    setLanguage(lang);
    i18n.changeLanguage(lang);
  };

  return (
    <div className="flag-toggle">
      {Object.entries(flags).map(([lang, emoji]) => (
        <button
          key={lang}
          onClick={() => switchLanguage(lang as "fr" | "en")}
          className={i18n.language === lang ? "active" : ""}
          aria-label={`Switch to ${lang}`}
        >
          {emoji}
        </button>
      ))}
    </div>
  );
}
