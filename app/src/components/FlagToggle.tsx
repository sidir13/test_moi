import { useSessionStore } from "@/hooks/useSessionStore";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

export function FlagToggle() {
  const { language, setLanguage } = useSessionStore();
  const { i18n } = useTranslation();

  const toggle = (lang: "fr" | "en") => {
    setLanguage(lang);
    i18n.changeLanguage(lang);
  };

  return (
    <div className="flex items-center gap-1 rounded-full border border-border bg-muted p-0.5">
      {(["fr", "en"] as const).map((lang) => (
        <button
          key={lang}
          type="button"
          onClick={() => toggle(lang)}
          className={cn(
            "rounded-full px-3 py-1 text-sm font-medium transition-all",
            language === lang
              ? "bg-white text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {lang === "fr" ? "🇫🇷 FR" : "🇬🇧 EN"}
        </button>
      ))}
    </div>
  );
}
