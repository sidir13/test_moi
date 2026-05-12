import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Loader2,
  Music,
  Pause,
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
  fetchAudioSelection,
  fetchBackgroundSounds,
  fetchScenarioAudio,
  fetchSelectedScenario,
  getBackgroundSoundPreviewUrl,
  getScenarioAudioUrl,
  remixScenarioAudio,
  saveAudioSelection,
  synthesizeScenarioAudio,
  uploadBackgroundSound,
  type BackgroundSound,
  type SfxPositionPayload,
} from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

// ─── Constants ───────────────────────────────────────────────────────────────

const PX_PER_SEC       = 15;
const LABEL_W          = 160;
const SFX_CLIP_DUR     = 15;
const CLIP_BASE_H      = 58;
const CLIP_BOTTOM_Y    = 63; // track height (68) - bottom padding (5)
const MIN_VOLUME_RATIO = 0.15;

// ─── Types ────────────────────────────────────────────────────────────────────

type ClipVariant = "Story" | "Ambient" | "Effet sonore" | "Ajouter";

type Clip = {
  id: string;
  label: string;
  variant: ClipVariant;
  start: number; // seconds
  end: number;   // seconds
  heightPx?: number;
  onClick?: () => void;
  onDragStart?: (e: React.MouseEvent) => void;
  onVolumeDragStart?: (e: React.MouseEvent) => void;
};

// ─── Styles ───────────────────────────────────────────────────────────────────

const CLIP_STYLES: Record<ClipVariant, { bg: string; border: string; text: string; dashed?: boolean }> = {
  Story:           { bg: "#eff6ff",     border: "#007aff", text: "#007aff" },
  Ambient:         { bg: "#cdffd1",     border: "#04a404", text: "#04a404" },
  "Effet sonore":  { bg: "#fdebf9",     border: "#c8009c", text: "#c8009c" },
  Ajouter:         { bg: "transparent", border: "#c8009c", text: "#c8009c", dashed: true },
};

// ─── AudioClip ───────────────────────────────────────────────────────────────

type AudioClipProps = {
  label: string;
  variant: ClipVariant;
  startPx: number;
  widthPx: number;
  heightPx?: number;
  onClick?: () => void;
  onDragStart?: (e: React.MouseEvent) => void;
  onVolumeDragStart?: (e: React.MouseEvent) => void;
};

function AudioClip({ label, variant, startPx, widthPx, heightPx = CLIP_BASE_H, onClick, onDragStart, onVolumeDragStart }: AudioClipProps) {
  const { bg, border, text, dashed } = CLIP_STYLES[variant];
  const isDraggable  = Boolean(onDragStart);
  const isResizable  = Boolean(onVolumeDragStart);
  const topPx        = CLIP_BOTTOM_Y - heightPx;

  return (
    <div
      className="absolute rounded-[6px] overflow-hidden select-none"
      style={{
        left: startPx,
        top: topPx,
        width: Math.max(widthPx, 36),
        height: heightPx,
        backgroundColor: bg,
        border: `1px ${dashed ? "dashed" : "solid"} ${border}`,
        color: text,
        cursor: isDraggable ? "grab" : onClick ? "pointer" : "default",
      }}
      onClick={!isDraggable && !isResizable ? onClick : undefined}
      onMouseDown={(e) => {
        if (onDragStart || onClick || onVolumeDragStart) e.stopPropagation();
        if (onDragStart) onDragStart(e);
      }}
    >
      {/* Volume resize handle at top */}
      {isResizable && (
        <div
          className="absolute inset-x-0 top-0 h-3 cursor-ns-resize z-10 flex items-center justify-center hover:bg-black/10 rounded-t-[5px]"
          onMouseDown={(e) => { e.stopPropagation(); onVolumeDragStart!(e); }}
        >
          <div className="w-6 h-[2px] rounded-full" style={{ backgroundColor: border, opacity: 0.55 }} />
        </div>
      )}

      {/* Label — hidden when too short */}
      {heightPx >= 24 && (
        <div className="flex items-center gap-2 px-3 h-full">
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
    <div className="relative h-[28px] border-b border-[#e2e8f0] bg-[#f8fafc]">
      {markers.map((t) => (
        <div
          key={t}
          className="absolute flex flex-col items-center"
          style={{ left: t * PX_PER_SEC, transform: "translateX(-50%)" }}
        >
          <div className="w-px h-[6px] bg-[#cbd5e1]" />
          <span className="text-[10px] text-[#94a3b8] mt-0.5 whitespace-nowrap">{t}s</span>
        </div>
      ))}
    </div>
  );
}

// ─── TrackContent ─────────────────────────────────────────────────────────────

function TrackContent({ clips }: { clips: Clip[] }) {
  return (
    <div className="relative h-[68px] border-b border-[#e2e8f0] last:border-b-0 bg-white">
      {clips.map((clip) => (
        <AudioClip
          key={clip.id}
          label={clip.label}
          variant={clip.variant}
          startPx={clip.start * PX_PER_SEC}
          widthPx={Math.max((clip.end - clip.start) * PX_PER_SEC, 36)}
          heightPx={clip.heightPx}
          onClick={clip.onClick}
          onDragStart={clip.onDragStart}
          onVolumeDragStart={clip.onVolumeDragStart}
        />
      ))}
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

// ─── Import sound modal ───────────────────────────────────────────────────────

function ImportSoundModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: (path: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const reset = () => { setTitle(""); setFile(null); setError(null); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setIsUploading(true);
    setError(null);
    try {
      const result = await uploadBackgroundSound(title.trim() || file.name.replace(/\.[^.]+$/, ""), file);
      reset();
      onSuccess(result.path as string);
      onClose();
    } catch {
      setError("Erreur lors de l'importation. Vérifiez le format du fichier.");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) { reset(); onClose(); } }}>
      <DialogContent className="w-[622px] max-w-[95vw] min-h-[490px] gap-[10px] rounded-[18px] border border-[#E2E8F0] bg-background p-6 shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
        <DialogHeader className="space-y-2">
          <DialogTitle className="text-[24px] font-semibold leading-[100%] text-foreground">
            Importer un son
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <label htmlFor="sound-title" className="text-[14px] font-semibold text-foreground">
              Nom du fichier
            </label>
            <input
              id="sound-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Ex: Bruits de foule, Ambiance marché…"
              className="h-11 rounded-[10px] border border-[#E2E8F0] bg-[#F4F4F4] px-3 text-sm text-foreground outline-none focus:border-[#007AFF]"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-[14px] font-semibold text-foreground">
              Fichier audio <span className="text-red-500">*</span>
            </label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp3,.wav,.m4a,audio/*"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex min-h-[230px] w-full flex-col items-center justify-center gap-3 rounded-[14px] border border-dashed border-blue-400/40 bg-background px-6 py-8 text-center transition-colors hover:bg-muted/30"
            >
              <Upload className="size-10 text-muted-foreground" />
              <div className="space-y-1">
                <p className="text-base font-medium text-[#45556C]">
                  {file ? file.name : "Cliquez pour télécharger"}
                </p>
                <p className="text-sm text-muted-foreground">MP3, WAV, M4A jusqu'à 100MB</p>
              </div>
            </button>
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={isUploading || !file}
              className="inline-flex h-[46px] items-center gap-1 rounded-[14px] bg-[#007AFF] px-6 text-base font-medium text-white transition-colors hover:bg-[#006ae0] disabled:opacity-50"
            >
              {isUploading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Importer
              <ChevronRight className="ml-1 h-4 w-4" />
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ─── SFX position state ───────────────────────────────────────────────────────

type SfxPos = { startSec: number; durationSec: number };

// ─── Main view ────────────────────────────────────────────────────────────────

export function ScenarioEditView() {
  const { sessionId, projectName, lastProjectName, updateProgress, setCurrentStep } = useSessionStore();
  const resolvedProjectName = projectName ?? lastProjectName;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [isPlaying, setIsPlaying]           = useState(false);
  const [currentTime, setCurrentTime]       = useState(0);
  const [audioDuration, setAudioDuration]   = useState<number | null>(null);
  const [audioKey, setAudioKey]             = useState(0);
  const [activeTab, setActiveTab]           = useState<GalleryTab>("Sons ambiants");
  const [searchQuery, setSearchQuery]       = useState("");
  const [showCategories, setShowCategories] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const [isGenerating, setIsGenerating]     = useState(false);
  const [isRemixing, setIsRemixing]         = useState(false);
  const [statusMsg, setStatusMsg]           = useState<string | null>(null);
  const [isScrubbingTimeline, setIsScrubbingTimeline] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [playingPreview, setPlayingPreview] = useState<string | null>(null);

  // SFX draggable positions
  const [sfxPositions, setSfxPositions]     = useState<Record<string, SfxPos>>({});
  const [clipDrag, setClipDrag]             = useState<{
    path: string;
    origStartSec: number;
    origMouseX: number;
  } | null>(null);

  // Clip volume levels (path → ratio 0..1, 1 = base, 0.15 = min)
  const [clipVolumes, setClipVolumes]       = useState<Record<string, number>>({});
  const [volumeDrag, setVolumeDrag]         = useState<{
    path: string;
    origRatio: number;
    origMouseY: number;
  } | null>(null);
  const clipVolumesRef                      = useRef<Record<string, number>>({});
  const sfxPositionsRef                     = useRef<Record<string, SfxPos>>({});

  const audioRef           = useRef<HTMLAudioElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const wasPlayingRef      = useRef(false);
  const previewAudioRef    = useRef<HTMLAudioElement | null>(null);

  // ── Queries ──────────────────────────────────────────────────────────────

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
  const audioSelectionQuery = useQuery({
    queryKey: ["audio-selection", sessionId],
    queryFn: () => fetchAudioSelection(sessionId!),
    enabled: Boolean(sessionId),
  });
  const soundsQuery = useQuery({
    queryKey: ["background-sounds", searchQuery],
    queryFn: () => fetchBackgroundSounds(searchQuery || undefined),
  });

  const audioJobStatus    = audioQuery.data?.status;
  const isAudioProcessing = audioJobStatus === "pending" || audioJobStatus === "running";
  const audioReady        = audioJobStatus === "done" && Boolean(audioQuery.data?.path);

  useEffect(() => {
    if (!sessionId || !isAudioProcessing) return;
    const iv = setInterval(() => audioQuery.refetch(), 4000);
    return () => clearInterval(iv);
  }, [sessionId, isAudioProcessing, audioQuery]);

  const audioSrc = useMemo(() => {
    if (!sessionId || !audioReady || !audioQuery.data?.path) return null;
    return `${getScenarioAudioUrl(sessionId)}?k=${audioKey}`;
  }, [audioQuery.data, sessionId, audioReady, audioKey]);

  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    if (isPlaying) el.play().catch(() => setIsPlaying(false));
    else el.pause();
  }, [isPlaying]);

  // Auto-scroll playhead into view during playback
  useEffect(() => {
    if (!isPlaying || !scrollContainerRef.current) return;
    const container = scrollContainerRef.current;
    const playheadPx = currentTime * PX_PER_SEC;
    const { scrollLeft, clientWidth } = container;
    if (playheadPx > scrollLeft + clientWidth - 80 || playheadPx < scrollLeft + 20) {
      container.scrollLeft = Math.max(0, playheadPx - clientWidth / 2);
    }
  }, [currentTime, isPlaying]);

  const totalDuration = audioDuration ?? 60;
  const timelineWidth = Math.max(totalDuration * PX_PER_SEC, 700);

  // Derived audio selection state
  const ambientPath   = audioSelectionQuery.data?.backgrounds?.ambient ?? null;
  const punctualPaths = audioSelectionQuery.data?.backgrounds?.punctual ?? [];
  const allSounds     = soundsQuery.data ?? [];

  // Initialise SFX positions when punctualPaths changes
  useEffect(() => {
    setSfxPositions((prev) => {
      const next: Record<string, SfxPos> = {};
      punctualPaths.forEach((path, i) => {
        next[path] = prev[path] ?? { startSec: i * (SFX_CLIP_DUR + 5), durationSec: SFX_CLIP_DUR };
      });
      return next;
    });
  }, [punctualPaths]);

  // Keep sfxPositionsRef in sync so drag/volume closures can read the latest positions
  useEffect(() => {
    sfxPositionsRef.current = sfxPositions;
  }, [sfxPositions]);

  // ── Clips ────────────────────────────────────────────────────────────────

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

  // Ambient clips — computed inline to include live volume state
  const ambientClips: Clip[] = [];
  if (ambientPath) {
    const ambientRatio = clipVolumes[ambientPath] ?? 1.0;
    const soundName =
      allSounds.find((s) => s.path === ambientPath)?.name ??
      ambientPath.split("/").pop()?.replace(/\.[^.]+$/, "") ??
      "Ambient";
    ambientClips.push({
      id: "amb0",
      label: soundName,
      variant: "Ambient",
      start: 0,
      end: totalDuration,
      heightPx: CLIP_BASE_H * ambientRatio,
      onVolumeDragStart: (e) => handleVolumeDragStart(ambientPath, ambientRatio, e),
    });
  }

  // SFX clips computed at render (not memoized — needs fresh drag handlers)
  const sfxClips: Clip[] = [];
  for (let i = 0; i < Math.min(punctualPaths.length, 3); i++) {
    const path = punctualPaths[i];
    const pos   = sfxPositions[path] ?? { startSec: i * (SFX_CLIP_DUR + 5), durationSec: SFX_CLIP_DUR };
    const ratio = clipVolumes[path] ?? 1.0;
    const name =
      allSounds.find((s) => s.path === path)?.name ??
      path.split("/").pop()?.replace(/\.[^.]+$/, "") ??
      `SFX ${i + 1}`;
    sfxClips.push({
      id: `sfx-${i}`,
      label: name,
      variant: "Effet sonore",
      start: pos.startSec,
      end: pos.startSec + pos.durationSec,
      heightPx: CLIP_BASE_H * ratio,
      onDragStart: (e) => handleSfxDragStart(path, pos.startSec, e),
      onVolumeDragStart: (e) => handleVolumeDragStart(path, ratio, e),
    });
  }
  if (punctualPaths.length < 3) {
    const i = punctualPaths.length;
    sfxClips.push({
      id: "sfx-add",
      label: "Ajouter un effet sonore",
      variant: "Ajouter",
      start: i * (SFX_CLIP_DUR + 5),
      end: i * (SFX_CLIP_DUR + 5) + SFX_CLIP_DUR,
      onClick: () => setShowImportModal(true),
    });
  }

  // ── Gallery ───────────────────────────────────────────────────────────────

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

  // ── Preview playback ──────────────────────────────────────────────────────

  const togglePreview = (sound: BackgroundSound) => {
    if (playingPreview === sound.path) {
      previewAudioRef.current?.pause();
      previewAudioRef.current = null;
      setPlayingPreview(null);
    } else {
      previewAudioRef.current?.pause();
      const audio = new Audio(getBackgroundSoundPreviewUrl(sound.path));
      audio.play().catch(() => {});
      audio.onended = () => setPlayingPreview(null);
      previewAudioRef.current = audio;
      setPlayingPreview(sound.path);
    }
  };

  useEffect(() => { return () => { previewAudioRef.current?.pause(); }; }, []);

  // ── Remix helpers ─────────────────────────────────────────────────────────

  const buildGainOverrides = (volumes: Record<string, number>): Record<string, number> | undefined => {
    const result: Record<string, number> = {};
    for (const [path, ratio] of Object.entries(volumes)) {
      if (ratio < 0.999) {
        result[path] = 20 * Math.log10(Math.max(ratio, 0.01));
      }
    }
    return Object.keys(result).length > 0 ? result : undefined;
  };

  const buildSfxPositions = (positions: Record<string, SfxPos>): SfxPositionPayload[] =>
    Object.entries(positions).map(([path, pos]) => ({
      path,
      start_seconds: pos.startSec,
      duration_seconds: pos.durationSec,
    }));

  const triggerRemix = async (gainOverrides?: Record<string, number>) => {
    if (!sessionId) return;
    setIsRemixing(true);
    const gains = gainOverrides ?? buildGainOverrides(clipVolumesRef.current);
    const positions = buildSfxPositions(sfxPositionsRef.current);
    try {
      await remixScenarioAudio(sessionId, gains, positions.length > 0 ? positions : undefined);
      setAudioKey((k) => k + 1);
      queryClient.invalidateQueries({ queryKey: ["scenario-audio", sessionId] });
    } finally {
      setIsRemixing(false);
    }
  };

  const selectAmbient = async (soundPath: string) => {
    if (!sessionId || !resolvedProjectName) return;
    const current = audioSelectionQuery.data;
    const newPath = ambientPath === soundPath ? null : soundPath;
    await saveAudioSelection(sessionId, {
      project_name: resolvedProjectName,
      voices: current?.voices ?? [],
      backgrounds: { ambient: newPath, punctual: current?.backgrounds?.punctual ?? [] },
      auto_backgrounds: current?.auto_backgrounds ?? false,
      tts_voice_id: current?.tts_voice_id,
      tts_provider: current?.tts_provider,
    });
    queryClient.invalidateQueries({ queryKey: ["audio-selection", sessionId] });
    await triggerRemix();
  };

  const addSfx = async (soundPath: string) => {
    if (!sessionId || !resolvedProjectName) return;
    const current = audioSelectionQuery.data;
    const existing = current?.backgrounds?.punctual ?? [];
    if (existing.includes(soundPath) || existing.length >= 3) return;
    const newPunctual = [...existing, soundPath];
    await saveAudioSelection(sessionId, {
      project_name: resolvedProjectName,
      voices: current?.voices ?? [],
      backgrounds: { ambient: current?.backgrounds?.ambient ?? null, punctual: newPunctual },
      auto_backgrounds: current?.auto_backgrounds ?? false,
      tts_voice_id: current?.tts_voice_id,
      tts_provider: current?.tts_provider,
    });
    queryClient.invalidateQueries({ queryKey: ["audio-selection", sessionId] });
    await triggerRemix();
  };

  const removeSfx = async (soundPath: string) => {
    if (!sessionId || !resolvedProjectName) return;
    const current = audioSelectionQuery.data;
    const newPunctual = (current?.backgrounds?.punctual ?? []).filter((p) => p !== soundPath);
    setSfxPositions((prev) => {
      const next = { ...prev };
      delete next[soundPath];
      return next;
    });
    await saveAudioSelection(sessionId, {
      project_name: resolvedProjectName,
      voices: current?.voices ?? [],
      backgrounds: { ambient: current?.backgrounds?.ambient ?? null, punctual: newPunctual },
      auto_backgrounds: current?.auto_backgrounds ?? false,
      tts_voice_id: current?.tts_voice_id,
      tts_provider: current?.tts_provider,
    });
    queryClient.invalidateQueries({ queryKey: ["audio-selection", sessionId] });
    await triggerRemix();
  };

  const toggleSfx = (soundPath: string) => {
    if (punctualPaths.includes(soundPath)) removeSfx(soundPath);
    else addSfx(soundPath);
  };

  // ── SFX clip dragging ─────────────────────────────────────────────────────

  const handleSfxDragStart = useCallback(
    (path: string, startSec: number, e: React.MouseEvent) => {
      e.stopPropagation();
      setClipDrag({ path, origStartSec: startSec, origMouseX: e.clientX });
    },
    [],
  );

  // ── Volume drag ───────────────────────────────────────────────────────────

  const handleVolumeDragStart = useCallback(
    (path: string, currentRatio: number, e: React.MouseEvent) => {
      e.stopPropagation();
      setVolumeDrag({ path, origRatio: currentRatio, origMouseY: e.clientY });
    },
    [],
  );

  useEffect(() => {
    if (!volumeDrag) return;
    const { path, origRatio, origMouseY } = volumeDrag;
    const origHeightPx = origRatio * CLIP_BASE_H;
    document.body.style.cursor    = "ns-resize";
    document.body.style.userSelect = "none";
    const onMove = (e: MouseEvent) => {
      const dy = e.clientY - origMouseY;
      const newRatio = Math.max(MIN_VOLUME_RATIO, Math.min(1.0, (origHeightPx - dy) / CLIP_BASE_H));
      clipVolumesRef.current = { ...clipVolumesRef.current, [path]: newRatio };
      setClipVolumes({ ...clipVolumesRef.current });
    };
    const onUp = () => {
      document.body.style.cursor    = "";
      document.body.style.userSelect = "";
      setVolumeDrag(null);
      const gains = buildGainOverrides(clipVolumesRef.current);
      const positions = buildSfxPositions(sfxPositionsRef.current);
      if (!sessionId) return;
      setIsRemixing(true);
      remixScenarioAudio(sessionId, gains, positions.length > 0 ? positions : undefined)
        .then(() => {
          setAudioKey((k) => k + 1);
          queryClient.invalidateQueries({ queryKey: ["scenario-audio", sessionId] });
        })
        .finally(() => setIsRemixing(false));
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.body.style.cursor    = "";
      document.body.style.userSelect = "";
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [volumeDrag, sessionId]);

  // Cursor during clip drag
  useEffect(() => {
    if (clipDrag) {
      document.body.style.cursor = "grabbing";
      document.body.style.userSelect = "none";
    } else {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }
    return () => {
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [clipDrag]);

  useEffect(() => {
    if (!clipDrag) return;
    const durSec = sfxPositions[clipDrag.path]?.durationSec ?? SFX_CLIP_DUR;
    const onMove = (e: MouseEvent) => {
      const dx = e.clientX - clipDrag.origMouseX;
      const newStart = Math.max(0, clipDrag.origStartSec + dx / PX_PER_SEC);
      const newPos: SfxPos = { startSec: newStart, durationSec: durSec };
      sfxPositionsRef.current = { ...sfxPositionsRef.current, [clipDrag.path]: newPos };
      setSfxPositions({ ...sfxPositionsRef.current });
    };
    const onUp = () => {
      setClipDrag(null);
      const gains = buildGainOverrides(clipVolumesRef.current);
      const positions = buildSfxPositions(sfxPositionsRef.current);
      if (!sessionId) return;
      setIsRemixing(true);
      remixScenarioAudio(sessionId, gains, positions.length > 0 ? positions : undefined)
        .then(() => {
          setAudioKey((k) => k + 1);
          queryClient.invalidateQueries({ queryKey: ["scenario-audio", sessionId] });
        })
        .finally(() => setIsRemixing(false));
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clipDrag, sessionId]);

  // ── Timeline scrubbing ────────────────────────────────────────────────────

  const computeTimeFromScrollX = (clientX: number): number => {
    const scrollLeft = scrollContainerRef.current?.scrollLeft ?? 0;
    const rect       = scrollContainerRef.current?.getBoundingClientRect();
    if (!rect) return 0;
    const x = clientX - rect.left + scrollLeft;
    return Math.max(0, Math.min(totalDuration, x / PX_PER_SEC));
  };

  const handleTimelineMouseDown = (e: React.MouseEvent) => {
    if (!audioSrc || clipDrag) return;
    wasPlayingRef.current = isPlaying;
    audioRef.current?.pause();
    setIsPlaying(false);
    setIsScrubbingTimeline(true);
    setCurrentTime(computeTimeFromScrollX(e.clientX));
  };

  useEffect(() => {
    if (!isScrubbingTimeline) return;
    const onMove = (e: MouseEvent) => setCurrentTime(computeTimeFromScrollX(e.clientX));
    const onUp = (e: MouseEvent) => {
      const t = computeTimeFromScrollX(e.clientX);
      setCurrentTime(t);
      if (audioRef.current) audioRef.current.currentTime = t;
      setIsScrubbingTimeline(false);
      if (wasPlayingRef.current) {
        audioRef.current?.play().catch(() => {});
        setIsPlaying(true);
      }
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isScrubbingTimeline, totalDuration]);

  // ── Validate ──────────────────────────────────────────────────────────────

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

  // ── Track label rows ──────────────────────────────────────────────────────

  const TRACK_LABELS = [
    { label: "Narration",     type: "Narration" },
    { label: "Ambient",       type: "Ambient" },
    { label: "Sound Effects", type: "Sound effects" },
  ];

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

        <div className="flex flex-col">

          {/* Action bar */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-[#e2e8f0]">
            <div className="flex items-center gap-3">
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
                    : <Play className="h-3.5 w-3.5 fill-current" />}
                </button>
              </div>

              <span className="text-[14px] font-semibold text-[#0f172b] tabular-nums">
                {fmtTime(currentTime)}
                <span className="mx-1.5 text-[#e2e8f0]">|</span>
                <span className="font-normal text-[#94a3b8]">{fmtTime(totalDuration)}</span>
              </span>

              <div className="flex items-center gap-1.5">
                <Volume2 className="h-3.5 w-3.5 text-[#94a3b8]" />
                <div className="relative h-1.5 w-20 rounded-full bg-[#e2e8f0]">
                  <div className="h-1.5 w-1/2 rounded-full bg-[#94a3b8]" />
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {(isAudioProcessing || isRemixing) && (
                <span className="flex items-center gap-1 text-[12px] text-[#64748b]">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {isRemixing ? "Remix…" : "En cours…"}
                </span>
              )}
              {statusMsg && !isAudioProcessing && !isRemixing && (
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

          {/* Timeline: fixed labels column + scrollable clip area */}
          <div className="flex border-t border-[#e2e8f0]">

            {/* Fixed labels column */}
            <div className="shrink-0 z-20 border-r border-[#e2e8f0]" style={{ width: LABEL_W }}>
              {/* Ruler placeholder row */}
              <div className="h-[28px] bg-[#f8fafc] border-b border-[#e2e8f0]" />
              {/* Track labels */}
              {TRACK_LABELS.map(({ label, type }) => (
                <div
                  key={label}
                  className="h-[68px] flex flex-col justify-center px-4 border-b border-[#e2e8f0] bg-[#f8fafc] last:border-b-0"
                >
                  <span className="text-[13px] font-semibold text-[#0f172b] leading-tight">{label}</span>
                  <span className="text-[11px] text-[#94a3b8] leading-tight mt-0.5">{type}</span>
                </div>
              ))}
            </div>

            {/* Scrollable clip area */}
            <div
              ref={scrollContainerRef}
              className="overflow-x-auto flex-1 relative"
              onMouseDown={handleTimelineMouseDown}
              style={{ cursor: clipDrag ? "grabbing" : audioSrc ? "col-resize" : "default" }}
            >
              {/* Playhead */}
              {totalDuration > 0 && (
                <div
                  className="absolute top-0 bottom-0 z-10 w-[2px] bg-[#007aff] opacity-80 pointer-events-none select-none"
                  style={{ left: currentTime * PX_PER_SEC }}
                >
                  <div className="absolute top-0 left-1/2 -translate-x-1/2 border-x-[5px] border-b-[6px] border-x-transparent border-b-[#007aff]" />
                </div>
              )}

              {/* Wide inner content */}
              <div style={{ width: timelineWidth }}>
                <TimeRuler totalDuration={totalDuration} />
                <div className="border-t border-[#e2e8f0]">
                  <TrackContent clips={narrationClips} />
                  <TrackContent clips={ambientClips} />
                  <TrackContent clips={sfxClips} />
                </div>
              </div>
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
            disabled={isGenerating || isAudioProcessing || isRemixing}
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
            key={audioSrc}
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
            onClick={() => setShowImportModal(true)}
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

          <div className="relative flex">
            <div className="flex-1">
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
                  {filteredSounds.map((sound) => {
                    const isAmbientSelected = ambientPath === sound.path;
                    const isSfxSelected     = punctualPaths.includes(sound.path);
                    const isSelected        = activeTab === "Sons ambiants" ? isAmbientSelected : isSfxSelected;
                    const isPreviewing      = playingPreview === sound.path;

                    return (
                      <div
                        key={sound.path}
                        role="button"
                        tabIndex={0}
                        onClick={() => {
                          if (activeTab === "Sons ambiants") selectAmbient(sound.path);
                          else toggleSfx(sound.path);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            if (activeTab === "Sons ambiants") selectAmbient(sound.path);
                            else toggleSfx(sound.path);
                          }
                        }}
                        className={`flex items-center justify-between px-5 py-2.5 cursor-pointer transition-colors hover:bg-[#f8fafc] focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#007aff] ${
                          isSelected ? "bg-[#eff6ff]" : ""
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <button
                            type="button"
                            aria-label={isPreviewing ? `Arrêter ${sound.name}` : `Écouter ${sound.name}`}
                            onClick={(e) => { e.stopPropagation(); togglePreview(sound); }}
                            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#e2e8f0] bg-white text-[#0f172b] hover:bg-[#f8fafc]"
                          >
                            {isPreviewing
                              ? <Pause className="h-3 w-3 fill-current" />
                              : <Play className="h-3 w-3 fill-current" />}
                          </button>
                          <span
                            className={`truncate text-[14px] ${
                              isSelected ? "font-medium text-[#007aff]" : "font-normal text-[#0f172b]"
                            }`}
                          >
                            {sound.name}
                          </span>
                        </div>
                        <span className="ml-4 shrink-0 text-[13px] text-[#94a3b8]">
                          {sound.category ?? "—"}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

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

      <ImportSoundModal
        open={showImportModal}
        onClose={() => setShowImportModal(false)}
        onSuccess={async (path) => {
          queryClient.invalidateQueries({ queryKey: ["background-sounds"] });
          await addSfx(path);
        }}
      />
    </div>
  );
}
