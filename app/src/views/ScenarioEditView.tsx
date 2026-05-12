import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Check,
  ChevronLeft,
  Loader2,
  Music,
  Play,
  Plus,
  Search,
  SkipBack,
  Square,
  Upload,
  Volume2,
  X,
} from "lucide-react";

import {
  advanceStep,
  fetchBackgroundSounds,
  fetchScenarioAudio,
  fetchSelectedScenario,
  getScenarioAudioUrl,
  synthesizeScenarioAudio,
} from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";

// ─── AudioClip ───────────────────────────────────────────────────────────────

type ClipVariant = "Story" | "Ambient" | "Effet sonore" | "Ajouter";

type Clip = {
  id: string;
  label: string;
  variant: ClipVariant;
  start: number; // seconds
  end: number;   // seconds
};

const CLIP_STYLES: Record<ClipVariant, { bg: string; border: string; text: string; dashed?: boolean }> = {
  Story:           { bg: "#eff6ff",     border: "#007aff", text: "#007aff" },
  Ambient:         { bg: "#cdffd1",     border: "#04a404", text: "#04a404" },
  "Effet sonore":  { bg: "#fdebf9",     border: "#c8009c", text: "#c8009c" },
  Ajouter:         { bg: "transparent", border: "#c8009c", text: "#c8009c", dashed: true },
};

type AudioClipProps = {
  label: string;
  variant: ClipVariant;
  start: number;
  end: number;
  totalDuration: number;
};

function AudioClip({ label, variant, start, end, totalDuration }: AudioClipProps) {
  const { bg, border, text, dashed } = CLIP_STYLES[variant];
  const leftPct = (start / totalDuration) * 100;
  const widthPct = Math.max(((end - start) / totalDuration) * 100, 0);

  return (
    <div
      className="absolute top-[5px] h-[58px] rounded-[6px] flex items-center gap-2 px-3 overflow-hidden select-none"
      style={{
        left: `${leftPct}%`,
        width: `${widthPct}%`,
        backgroundColor: bg,
        border: `1px ${dashed ? "dashed" : "solid"} ${border}`,
        color: text,
        minWidth: 36,
      }}
    >
      {variant === "Ajouter" ? (
        <span className="flex items-center gap-1 text-[13px] font-normal whitespace-nowrap">
          <Plus className="h-3 w-3 shrink-0" />
          {label}
        </span>
      ) : (
        <span className="text-[13px] font-semibold whitespace-nowrap overflow-hidden text-ellipsis">
          {label}
        </span>
      )}
    </div>
  );
}

// ─── Time ruler ──────────────────────────────────────────────────────────────

function TimeRuler({ totalDuration }: { totalDuration: number }) {
  const step = totalDuration <= 10 ? 1 : totalDuration <= 30 ? 5 : totalDuration <= 120 ? 10 : 30;
  const markers: number[] = [];
  for (let t = 0; t <= totalDuration; t += step) markers.push(t);

  return (
    <div className="relative h-[28px] w-full border-b border-[#e2e8f0] bg-[#f8fafc]">
      {markers.map((t) => {
        const pct = (t / totalDuration) * 100;
        return (
          <div
            key={t}
            className="absolute flex flex-col items-center"
            style={{ left: `${pct}%`, transform: "translateX(-50%)" }}
          >
            <div className="w-px h-[6px] bg-[#cbd5e1]" />
            <span className="text-[10px] text-[#94a3b8] mt-0.5 whitespace-nowrap">{t}s</span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Track ───────────────────────────────────────────────────────────────────

const LABEL_W = 160;

function Track({
  label,
  type,
  clips,
  totalDuration,
}: {
  label: string;
  type: string;
  clips: Clip[];
  totalDuration: number;
}) {
  return (
    <div className="flex h-[68px] border-b border-[#e2e8f0] last:border-b-0">
      <div
        className="shrink-0 flex flex-col justify-center px-4 border-r border-[#e2e8f0] bg-[#f8fafc]"
        style={{ width: LABEL_W }}
      >
        <span className="text-[13px] font-semibold text-[#0f172b] leading-tight">{label}</span>
        <span className="text-[11px] text-[#94a3b8] leading-tight mt-0.5">{type}</span>
      </div>
      <div className="relative flex-1 overflow-hidden bg-white">
        {clips.map((clip) => (
          <AudioClip
            key={clip.id}
            label={clip.label}
            variant={clip.variant}
            start={clip.start}
            end={clip.end}
            totalDuration={totalDuration}
          />
        ))}
      </div>
    </div>
  );
}

// ─── Gallery tabs ─────────────────────────────────────────────────────────────

type GalleryTab = "Sons ambiants" | "Effets sonores" | "Mes sons";
const GALLERY_TABS: GalleryTab[] = ["Sons ambiants", "Effets sonores", "Mes sons"];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtTime(s: number): string {
  const hh = Math.floor(s / 3600).toString().padStart(2, "0");
  const mm = Math.floor((s % 3600) / 60).toString().padStart(2, "0");
  const ss = Math.floor(s % 60).toString().padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

function extractPayload(raw: Record<string, unknown>): Record<string, unknown> {
  if (raw.scenario && typeof raw.scenario === "object") return raw.scenario as Record<string, unknown>;
  return raw;
}

// ─── Main view ────────────────────────────────────────────────────────────────

export function ScenarioEditView() {
  const { sessionId, updateProgress, setCurrentStep } = useSessionStore();
  const navigate = useNavigate();

  const [isPlaying, setIsPlaying]       = useState(false);
  const [currentTime, setCurrentTime]   = useState(0);
  const [audioDuration, setAudioDuration] = useState<number | null>(null);
  const [selectedBackground, setSelectedBackground] = useState<string | null>(null);
  const [activeTab, setActiveTab]         = useState<GalleryTab>("Sons ambiants");
  const [searchQuery, setSearchQuery]     = useState("");
  const [showCategories, setShowCategories] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const [isGenerating, setIsGenerating]   = useState(false);
  const [statusMsg, setStatusMsg]         = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const selectionQuery = useQuery({
    queryKey: ["selected-scenario", sessionId],
    queryFn: () => fetchSelectedScenario(sessionId!),
    enabled: Boolean(sessionId),
  });
  const audioQuery = useQuery({
    queryKey: ["scenario-audio", sessionId],
    queryFn: () => fetchScenarioAudio(sessionId!),
    enabled: Boolean(sessionId),
  });
  const soundsQuery = useQuery({
    queryKey: ["background-sounds", searchQuery],
    queryFn: () => fetchBackgroundSounds(searchQuery || undefined),
  });

  const audioJobStatus  = audioQuery.data?.status;
  const isAudioProcessing = audioJobStatus === "pending" || audioJobStatus === "running";
  const audioReady      = audioJobStatus === "done" && Boolean(audioQuery.data?.path);

  useEffect(() => {
    if (!sessionId || !isAudioProcessing) return;
    const iv = setInterval(() => audioQuery.refetch(), 4000);
    return () => clearInterval(iv);
  }, [sessionId, isAudioProcessing, audioQuery]);

  const audioSrc = useMemo(() => {
    if (!sessionId || !audioReady || !audioQuery.data?.path) return null;
    const base = getScenarioAudioUrl(sessionId).replace(/\/$/, "");
    const ts = audioQuery.data.generated_at
      ? `?ts=${encodeURIComponent(audioQuery.data.generated_at)}`
      : "";
    return `${base}${ts}`;
  }, [audioQuery.data, sessionId, audioReady]);

  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    if (isPlaying) el.play().catch(() => setIsPlaying(false));
    else el.pause();
  }, [isPlaying]);

  const totalDuration = audioDuration ?? 60;

  // Narration clips from scenario parts
  const narrationClips = useMemo((): Clip[] => {
    if (!selectionQuery.data) {
      return [{ id: "n0", label: "Story", variant: "Story", start: 0, end: totalDuration }];
    }
    const raw = selectionQuery.data as Record<string, unknown>;
    const payload = extractPayload(raw);
    const parts = Array.isArray(payload.parties)
      ? (payload.parties as Array<Record<string, unknown>>)
      : null;

    if (!parts || parts.length === 0) {
      return [{ id: "n0", label: "Story", variant: "Story", start: 0, end: totalDuration }];
    }

    const texts = parts.map((p) => ((p.texte_narration ?? p.texte) as string) ?? "");
    const totalChars = texts.reduce((sum, t) => sum + t.length, 0) || 1;
    let cursor = 0;
    return parts.map((p, idx) => {
      const dur = (texts[idx].length / totalChars) * totalDuration;
      const clip: Clip = {
        id: `n${idx}`,
        label: (p.titre as string) ?? `Partie ${idx + 1}`,
        variant: "Story",
        start: cursor,
        end: cursor + dur,
      };
      cursor += dur;
      return clip;
    });
  }, [selectionQuery.data, totalDuration]);

  const ambientClips = useMemo((): Clip[] => {
    if (!selectedBackground) return [];
    return [{ id: "amb0", label: selectedBackground, variant: "Ambient", start: 0, end: totalDuration }];
  }, [selectedBackground, totalDuration]);

  const sfxClips: Clip[] = [
    { id: "sfx-add", label: "Ajouter un effet sonore", variant: "Ajouter", start: 0, end: totalDuration * 0.18 },
  ];

  // Gallery data
  const allSounds = soundsQuery.data ?? [];
  const categories = useMemo(() => {
    const cats = new Set(allSounds.map((s) => s.category).filter(Boolean) as string[]);
    return Array.from(cats);
  }, [allSounds]);

  const filteredSounds = useMemo(() => {
    let list = allSounds;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter((s) => s.name.toLowerCase().includes(q));
    }
    if (selectedCategories.size > 0) {
      list = list.filter((s) => s.category && selectedCategories.has(s.category));
    }
    return list;
  }, [allSounds, searchQuery, selectedCategories]);

  const toggleCategory = (cat: string) => {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      next.has(cat) ? next.delete(cat) : next.add(cat);
      return next;
    });
  };

  const handleValidate = async () => {
    if (!sessionId) return;
    setIsGenerating(true);
    setStatusMsg("Génération de l'audio…");
    try {
      await synthesizeScenarioAudio(sessionId);
      await audioQuery.refetch();
      await advanceStep(sessionId, "scenario_edit", {});
      updateProgress({ scenarioEdited: true });
      setCurrentStep("final_validation");
      navigate("/step/final_validation");
    } catch {
      setStatusMsg("Erreur lors de la génération. Réessayez.");
      setIsGenerating(false);
    }
  };

  if (!sessionId) return null;

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-4">

      {/* ── Block 1 – Timeline ─────────────────────────────────────────────── */}
      <div className="rounded-[14px] border border-[#8ea4bd] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)] overflow-hidden">

        {/* Header */}
        <div className="flex items-center gap-2 border-b border-[#e2e8f0] bg-[#f8fafc] px-5 py-4">
          <Music className="h-4 w-4 text-[#45556c] shrink-0" />
          <div className="flex flex-col gap-0.5">
            <h2 className="text-[14px] font-medium text-[#45556c] leading-none">Édition de l'audio</h2>
            <p className="text-[13px] text-[#94a3b8] leading-none">
              Personnaliser l'audio pour le transformer en artefact.
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-0">

          {/* Action bar */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-[#e2e8f0]">
            {/* Left: transport controls + time + volume */}
            <div className="flex items-center gap-3">
              {/* Transport */}
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => { if (audioRef.current) audioRef.current.currentTime = 0; setCurrentTime(0); }}
                  className="flex h-8 w-8 items-center justify-center rounded-md text-[#45556c] hover:bg-[#f1f5f9]"
                  aria-label="Retour au début"
                >
                  <SkipBack className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setIsPlaying((v) => !v)}
                  disabled={!audioSrc}
                  className="flex h-8 w-8 items-center justify-center rounded-full bg-[#007aff] text-white hover:bg-[#006ae0] disabled:opacity-40"
                  aria-label={isPlaying ? "Pause" : "Lecture"}
                >
                  {isPlaying
                    ? <Square className="h-3.5 w-3.5 fill-current" />
                    : <Play className="h-3.5 w-3.5 fill-current" />
                  }
                </button>
              </div>

              {/* Time */}
              <span className="text-[14px] font-semibold text-[#0f172b] tabular-nums">
                {fmtTime(currentTime)}
                <span className="mx-1.5 text-[#e2e8f0]">|</span>
                <span className="font-normal text-[#94a3b8]">{fmtTime(totalDuration)}</span>
              </span>

              {/* Volume */}
              <div className="flex items-center gap-1.5">
                <Volume2 className="h-3.5 w-3.5 text-[#94a3b8]" />
                <div className="relative h-1.5 w-20 rounded-full bg-[#e2e8f0]">
                  <div className="h-1.5 w-1/2 rounded-full bg-[#94a3b8]" />
                </div>
              </div>
            </div>

            {/* Right: X reset + add track + status */}
            <div className="flex items-center gap-2">
              {isAudioProcessing && (
                <span className="flex items-center gap-1 text-[12px] text-[#64748b]">
                  <Loader2 className="h-3 w-3 animate-spin" /> En cours…
                </span>
              )}
              {statusMsg && !isAudioProcessing && (
                <span className="text-[12px] text-[#64748b]">{statusMsg}</span>
              )}
              <button
                type="button"
                onClick={() => { setCurrentTime(0); if (audioRef.current) audioRef.current.currentTime = 0; }}
                className="flex h-7 w-7 items-center justify-center rounded-md text-[#94a3b8] hover:bg-[#f1f5f9] hover:text-[#45556c]"
                aria-label="Réinitialiser"
              >
                <X className="h-4 w-4" />
              </button>
              <button
                type="button"
                className="inline-flex h-8 items-center gap-1.5 rounded-[8px] border border-[#e2e8f0] bg-white px-3 text-[13px] font-medium text-[#45556c] hover:bg-[#f8fafc]"
              >
                <Plus className="h-3.5 w-3.5" />
                Ajouter une piste
              </button>
            </div>
          </div>

          {/* Ruler + tracks (shared relative container for playhead) */}
          <div className="relative">
            {/* Playhead — spans ruler + all tracks */}
            {totalDuration > 0 && (
              <div
                className="pointer-events-none absolute top-0 bottom-0 z-10 w-[2px] bg-[#007aff] opacity-80"
                style={{
                  left: `calc(${LABEL_W}px + (100% - ${LABEL_W}px) * ${currentTime / totalDuration})`,
                }}
              >
                {/* Small triangle at top */}
                <div className="absolute -top-0 left-1/2 -translate-x-1/2 border-x-[5px] border-b-[6px] border-x-transparent border-b-[#007aff]" />
              </div>
            )}

            {/* Ruler row */}
            <div className="flex">
              <div
                className="shrink-0 border-r border-[#e2e8f0] bg-[#f8fafc]"
                style={{ width: LABEL_W }}
              />
              <div className="flex-1">
                <TimeRuler totalDuration={totalDuration} />
              </div>
            </div>

            {/* Tracks */}
            <div className="border-t border-[#e2e8f0]">
              <Track label="Narration"     type="Narration"     clips={narrationClips} totalDuration={totalDuration} />
              <Track label="Ambient"       type="Ambient"       clips={ambientClips}   totalDuration={totalDuration} />
              <Track label="Sound Effects" type="Sound effects" clips={sfxClips}        totalDuration={totalDuration} />
            </div>
          </div>
        </div>

        {/* Validate button */}
        <div className="flex items-center justify-end gap-3 border-t border-[#e2e8f0] px-5 py-3">
          {isGenerating && (
            <span className="flex items-center gap-1.5 text-[13px] text-[#64748b]">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Génération…
            </span>
          )}
          <button
            type="button"
            onClick={handleValidate}
            disabled={isGenerating || isAudioProcessing}
            className="inline-flex h-[38px] items-center gap-1.5 rounded-[12px] bg-[#007aff] px-5 text-[14px] font-medium text-white hover:bg-[#006ae0] disabled:opacity-50"
          >
            {isGenerating ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Check className="h-3.5 w-3.5" />
            )}
            Valider version finale
          </button>
        </div>

        {/* Hidden audio */}
        {audioSrc && (
          <audio
            ref={audioRef}
            src={audioSrc}
            className="hidden"
            onLoadedMetadata={(e) =>
              setAudioDuration((e.target as HTMLAudioElement).duration || null)
            }
            onTimeUpdate={(e) =>
              setCurrentTime((e.target as HTMLAudioElement).currentTime)
            }
            onEnded={() => setIsPlaying(false)}
          />
        )}
      </div>

      {/* ── Block 2 – Audio gallery ────────────────────────────────────────── */}
      <div className="rounded-[14px] border border-[#8ea4bd] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)] overflow-hidden">

        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#e2e8f0] bg-[#f8fafc] px-5 py-4">
          <div className="flex items-center gap-2">
            <Music className="h-4 w-4 text-[#45556c] shrink-0" />
            <div className="flex flex-col gap-0.5">
              <h2 className="text-[14px] font-medium text-[#45556c] leading-none">Galerie audio</h2>
              <p className="text-[13px] text-[#94a3b8] leading-none">
                Choisissez le scénario qui correspond le mieux à vos objectifs de médiation
              </p>
            </div>
          </div>
          <button
            type="button"
            className="inline-flex h-[38px] items-center gap-1.5 rounded-[12px] bg-[#007aff] px-4 text-[14px] font-medium text-white hover:bg-[#006ae0]"
          >
            <Upload className="h-3.5 w-3.5" />
            Importer un fichier audio
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[#e2e8f0] px-5">
          {GALLERY_TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveTab(tab)}
              className={`relative py-3 px-4 text-[13px] font-medium transition-colors ${
                activeTab === tab
                  ? "text-[#007aff] after:absolute after:bottom-0 after:left-0 after:right-0 after:h-[2px] after:bg-[#007aff]"
                  : "text-[#94a3b8] hover:text-[#45556c]"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Search + list */}
        <div className="flex flex-col gap-0">
          {/* Search bar */}
          <div className="flex items-center gap-2 border-b border-[#e2e8f0] px-5 py-2.5">
            <Search className="h-4 w-4 shrink-0 text-[#94a3b8]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Rechercher une piste audio ou filtrer la bibliothèque"
              className="flex-1 bg-transparent text-[14px] text-[#0f172b] outline-none placeholder:text-[#94a3b8]"
            />
          </div>

          {/* List + optional category panel */}
          <div className="relative flex">
            {/* Sound list */}
            <div className="flex-1">
              {/* Column headers */}
              <div className="flex items-center justify-between px-5 py-2 border-b border-[#e2e8f0] bg-[#f8fafc]">
                <button
                  type="button"
                  onClick={() => setShowCategories((v) => !v)}
                  className="flex items-center gap-1.5 text-[12px] font-medium text-[#45556c] hover:text-[#0f172b]"
                >
                  <ChevronLeft
                    className={`h-3.5 w-3.5 transition-transform ${showCategories ? "rotate-180" : ""}`}
                  />
                  Catégories
                </button>
                <span className="text-[12px] text-[#94a3b8]">Catégorie</span>
              </div>

              {soundsQuery.isLoading ? (
                <div className="flex items-center justify-center gap-2 py-10 text-[13px] text-[#94a3b8]">
                  <Loader2 className="h-4 w-4 animate-spin" /> Chargement…
                </div>
              ) : filteredSounds.length === 0 ? (
                <p className="py-10 text-center text-[13px] text-[#94a3b8]">
                  Aucune piste disponible.
                </p>
              ) : (
                <div className="divide-y divide-[#e2e8f0]">
                  {filteredSounds.map((sound) => (
                    <div
                      key={sound.name}
                      role="button"
                      tabIndex={0}
                      onClick={() =>
                        setSelectedBackground(
                          selectedBackground === sound.name ? null : sound.name
                        )
                      }
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          setSelectedBackground(
                            selectedBackground === sound.name ? null : sound.name
                          );
                        }
                      }}
                      className={`flex items-center justify-between px-5 py-2.5 cursor-pointer transition-colors hover:bg-[#f8fafc] focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#007aff] ${
                        selectedBackground === sound.name ? "bg-[#eff6ff]" : ""
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <button
                          type="button"
                          aria-label={`Écouter ${sound.name}`}
                          onClick={(e) => e.stopPropagation()}
                          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#e2e8f0] bg-white text-[#0f172b] hover:bg-[#f8fafc]"
                        >
                          <Play className="h-3 w-3 fill-current" />
                        </button>
                        <span
                          className={`truncate text-[14px] ${
                            selectedBackground === sound.name
                              ? "font-medium text-[#007aff]"
                              : "font-normal text-[#0f172b]"
                          }`}
                        >
                          {sound.name}
                        </span>
                      </div>
                      <span className="ml-4 shrink-0 text-[13px] text-[#94a3b8]">
                        {sound.category ?? "—"}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Category filter panel */}
            {showCategories && categories.length > 0 && (
              <div className="w-[220px] shrink-0 border-l border-[#e2e8f0]">
                <div className="border-b border-[#e2e8f0] px-4 py-2.5">
                  <span className="text-[12px] font-semibold text-[#45556c]">Catégories</span>
                </div>
                <div className="flex flex-col divide-y divide-[#e2e8f0]">
                  {categories.map((cat) => (
                    <label
                      key={cat}
                      className="flex cursor-pointer items-center justify-between px-4 py-3 hover:bg-[#f8fafc]"
                    >
                      <span className="text-[13px] text-[#0f172b]">{cat}</span>
                      <input
                        type="checkbox"
                        checked={selectedCategories.has(cat)}
                        onChange={() => toggleCategory(cat)}
                        className="h-4 w-4 rounded border-[#d1d5db] accent-[#007aff]"
                      />
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
