import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Save, ChevronRight, FileText, Plus, Download, X, ChevronDown, Play, Pause, Volume2, VolumeX, Network, Eye, Sparkles } from "lucide-react";

import {
  advanceStep,
  fetchProjectAudio,
  fetchProjectProfile,
  fetchProjectTranscriptions,
  fetchProjectKnowledgeGraph,
  getProjectAudioFileUrl,
  getProjectTranscriptionBundleUrl,
  getProjectKnowledgeGraphViewUrl
} from "@/api/client";
import { useSessionStore } from "@/hooks/useSessionStore";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";

const DEFAULT_DURATION_SECONDS = 120;
const MIN_DURATION_SECONDS = 30;

const formatOptionLabel = (value: string) =>
  value
    .split("_")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");

const formatDuration = (seconds: number) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return [mins > 0 ? `${mins} min` : "", `${secs.toString().padStart(2, "0")} s`]
    .filter(Boolean)
    .join(" ");
};

export function ProjectDetailsView() {
  const { sessionId, projectName, setCurrentStep, setProgress } = useSessionStore();
  const navigate = useNavigate();

  const [notes, setNotes] = useState("");
  const [audience, setAudience] = useState("");
  const [tone, setTone] = useState("");
  const [voiceInstructions, setVoiceInstructions] = useState("");
  const [targetDuration, setTargetDuration] = useState(DEFAULT_DURATION_SECONDS);
  const [ttsProvider, setTtsProvider] = useState<"qwen" | "elevenlabs">("elevenlabs");
  const [includeCitations, setIncludeCitations] = useState(true);
  const [sourceUsageLevel, setSourceUsageLevel] = useState<"leger" | "modere" | "central">("modere");
  const [status, setStatus] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [showTranscriptionBlock, setShowTranscriptionBlock] = useState(true);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [audioPlaying, setAudioPlaying] = useState(false);
  const [audioMuted, setAudioMuted] = useState(false);
  const [audioCurrent, setAudioCurrent] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);

  const notesPrefilledFor = useRef<string | null>(null);
  const progressPrefilledFor = useRef<string | null>(null);
  const preferencesPrefilledFor = useRef<string | null>(null);

  const profileQuery = useQuery({
    queryKey: ["project-profile", projectName],
    queryFn: () => fetchProjectProfile(projectName!),
    enabled: Boolean(projectName)
  });
  const projectAudioQuery = useQuery({
    queryKey: ["project-audio-files", projectName],
    queryFn: () => fetchProjectAudio(projectName!),
    enabled: Boolean(projectName),
  });
  const transcriptionsQuery = useQuery({
    queryKey: ["project-transcriptions", projectName],
    queryFn: () => fetchProjectTranscriptions(projectName!),
    enabled: Boolean(projectName),
  });
  const knowledgeGraphQuery = useQuery({
    queryKey: ["project-knowledge-graph", projectName],
    queryFn: () => fetchProjectKnowledgeGraph(projectName!),
    enabled: Boolean(projectName),
  });
  const mockTranscriptionsQuery = useQuery({
    queryKey: ["mock-transcriptions"],
    queryFn: async () => {
      const response = await fetch("/mocks/transcriptions.json");
      if (!response.ok) throw new Error("Impossible de charger le mock transcriptions");
      return response.json() as Promise<{
        transcriptions: Array<{
          file_name: string;
          transcription: string;
          summary?: { global_summary?: string; topics?: Array<{ title: string }> };
        }>;
      }>;
    },
  });
  const mockDetailsQuery = useQuery({
    queryKey: ["project-details-mock"],
    queryFn: async () => {
      const response = await fetch("/mocks/project-details.json");
      if (!response.ok) throw new Error("Impossible de charger le mock project-details");
      return response.json() as Promise<{
        transcriptionBlock?: {
          subtitle?: string;
          fallbackFileName?: string;
          fallbackTopics?: string[];
          fallbackTitle?: string;
          fallbackText?: string;
        };
        knowledgeGraph?: { title?: string; subtitle?: string; keywordsCount?: number };
        artifacts?: { title?: string; subtitle?: string; emptyState?: boolean };
      }>;
    },
  });

  useEffect(() => {
    if (!projectName) {
      notesPrefilledFor.current = null;
      progressPrefilledFor.current = null;
      preferencesPrefilledFor.current = null;
    }
  }, [projectName]);

  useEffect(() => {
    setShowTranscriptionBlock(true);
  }, [projectName]);

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent<{ text: string }>).detail;
      if (typeof detail?.text === "string" && detail.text.length > 0) {
        setNotes(detail.text);
        (window as Window & { __projectNotes?: string }).__projectNotes = detail.text;
        // Reset guard so query refetch (invalidateQueries fallback) also applies fresh data
        notesPrefilledFor.current = null;
      }
    };
    window.addEventListener("project-notes-updated", handler);
    return () => window.removeEventListener("project-notes-updated", handler);
  }, []);

  useEffect(() => {
    if (!projectName || !profileQuery.data) return;
    if (notesPrefilledFor.current === projectName) return;
    setNotes(profileQuery.data.project_notes ?? "");
    (window as Window & { __projectNotes?: string }).__projectNotes = profileQuery.data.project_notes ?? "";
    notesPrefilledFor.current = projectName;
  }, [profileQuery.data, projectName]);

  useEffect(() => {
    if (!projectName || !profileQuery.data) return;
    if (preferencesPrefilledFor.current === projectName) return;
    const pref = profileQuery.data.preference_options;
    const ds = pref?.duration;
    const clamp = (v: number) => (ds ? Math.min(ds.max, Math.max(ds.min, v)) : v);
    setAudience(profileQuery.data.audience ?? "");
    setTone(profileQuery.data.tone ?? "");
    setVoiceInstructions(profileQuery.data.voice_instructions ?? "");
    setTtsProvider(profileQuery.data.tts_provider === "qwen" ? "qwen" : "elevenlabs");
    setIncludeCitations(profileQuery.data.include_citations !== false);
    const savedLevel = profileQuery.data.source_usage_level;
    if (savedLevel === "leger" || savedLevel === "modere" || savedLevel === "central") {
      setSourceUsageLevel(savedLevel);
    }
    const raw =
      profileQuery.data.target_duration ?? ds?.default ?? DEFAULT_DURATION_SECONDS;
    setTargetDuration(clamp(typeof raw === "number" ? raw : DEFAULT_DURATION_SECONDS));
    preferencesPrefilledFor.current = projectName;
  }, [profileQuery.data, projectName]);

  useEffect(() => {
    if (!projectName || !profileQuery.data) return;
    if (progressPrefilledFor.current === projectName) return;
    const hasStored = Boolean(profileQuery.data.last_scenarios?.length);
    const hasFinal = Boolean(profileQuery.data.final_scenario);
    const hasTranscriptions = Boolean(transcriptionsQuery.data?.length);
    const hasProjectAudio = Boolean(projectAudioQuery.data?.length);
    setProgress({
      audioReady: Boolean(
        profileQuery.data.final_audio?.path ||
          profileQuery.data.audio_selection?.voices?.length ||
          hasTranscriptions ||
          hasProjectAudio
      ),
      transcriptionsReviewed:
        Boolean(profileQuery.data.final_audio?.path) || hasStored || hasFinal || hasTranscriptions,
      scenariosReady: hasStored || hasFinal,
      scenarioChosen: hasFinal,
      scenarioEdited: false
    });
    progressPrefilledFor.current = projectName;
  }, [profileQuery.data, projectName, setProgress, transcriptionsQuery.data, projectAudioQuery.data]);

  const preferenceOptions = profileQuery.data?.preference_options;
  const toneOptions = preferenceOptions?.tone_options ?? [];
  const audienceOptions = preferenceOptions?.audience_options ?? [];

  const durationSettings = useMemo(() => {
    const configuredMin = preferenceOptions?.duration?.min;
    const enforcedMin = Math.min(
      typeof configuredMin === "number" ? configuredMin : MIN_DURATION_SECONDS,
      MIN_DURATION_SECONDS
    );
    return {
      min: enforcedMin,
      max: preferenceOptions?.duration?.max ?? 600,
      step: preferenceOptions?.duration?.step ?? 10
    };
  }, [preferenceOptions]);

  const sliderRangeLabel = useMemo(() => {
    const fmt = (v: number) => (v % 60 === 0 ? `${v / 60} min` : `${v}s`);
    return `${fmt(durationSettings.min)} – ${fmt(durationSettings.max)}`;
  }, [durationSettings]);
  const audioFiles = projectAudioQuery.data ?? mockTranscriptionsQuery.data?.transcriptions.map((t) => t.file_name) ?? [];
  const firstAudioFile = audioFiles[0];
  const transcriptionEntries = transcriptionsQuery.data?.length
    ? transcriptionsQuery.data
    : (mockTranscriptionsQuery.data?.transcriptions ?? []);
  const firstTranscription =
    transcriptionEntries.find((entry) => entry.file_name === firstAudioFile) ?? transcriptionEntries[0];
  const transcriptionTopics =
    firstTranscription?.summary?.topics?.slice(0, 4).map((topic) => topic.title).filter(Boolean) ?? [];
  const fallbackTopics =
    mockDetailsQuery.data?.transcriptionBlock?.fallbackTopics ??
    ["Vie quotidienne", "Mémoire ouvrière", "Chantiers navals", "Patrimoine local"];
  const displayedTags = transcriptionTopics.length > 0 ? transcriptionTopics : fallbackTopics;
  const transcriptionText =
    firstTranscription?.transcription?.trim() ||
    mockDetailsQuery.data?.transcriptionBlock?.fallbackText ||
    "La transcription apparaîtra ici après l’upload et le traitement automatique du fichier audio.";
  const transcriptionTitle = mockDetailsQuery.data?.transcriptionBlock?.fallbackTitle ?? "Souvenir des chantiers de Nantes";
  const transcriptionSubtitle =
    mockDetailsQuery.data?.transcriptionBlock?.subtitle ?? "Lire et modifier la transcription des fichiers audio.";
  const fallbackFileName = mockDetailsQuery.data?.transcriptionBlock?.fallbackFileName ?? "interview_001.mp3";
  const knowledgeGraphTitle = mockDetailsQuery.data?.knowledgeGraph?.title ?? "Knowledge Graph";
  const knowledgeGraphSubtitle =
    mockDetailsQuery.data?.knowledgeGraph?.subtitle ?? "Lire et modifier les transcriptions des fichiers audio.";
  const keywordsCount = mockDetailsQuery.data?.knowledgeGraph?.keywordsCount ?? 39;
  const artifactsTitle = mockDetailsQuery.data?.artifacts?.title ?? "Mes Artefacts";
  const artifactsSubtitle =
    mockDetailsQuery.data?.artifacts?.subtitle ?? "Lire et modifier les transcriptions des fichiers audio.";

  const audioSrc = projectName && firstAudioFile ? getProjectAudioFileUrl(projectName, firstAudioFile) : null;

  useEffect(() => {
    setAudioPlaying(false);
    setAudioCurrent(0);
    setAudioDuration(0);
  }, [audioSrc]);

  const togglePlay = () => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) {
      void el.play();
    } else {
      el.pause();
    }
  };

  const toggleMute = () => {
    const el = audioRef.current;
    if (!el) return;
    el.muted = !el.muted;
    setAudioMuted(el.muted);
  };

  const seekTo = (evt: React.MouseEvent<HTMLDivElement>) => {
    const el = audioRef.current;
    if (!el || !audioDuration) return;
    const rect = evt.currentTarget.getBoundingClientRect();
    const ratio = Math.min(Math.max((evt.clientX - rect.left) / rect.width, 0), 1);
    el.currentTime = ratio * audioDuration;
    setAudioCurrent(el.currentTime);
  };

  const formatClock = (seconds: number) => {
    if (!Number.isFinite(seconds)) return "0:00";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const audioProgressPct = audioDuration > 0 ? (audioCurrent / audioDuration) * 100 : 0;

  const knowledgeGraphNodeCount = knowledgeGraphQuery.data?.graph?.nodes?.length ?? 0;
  const knowledgeGraphKeywordCount =
    knowledgeGraphQuery.data?.graph?.nodes?.filter((n) => n.type === "Keyword").length ?? 0;
  const knowledgeGraphViewUrl = projectName ? getProjectKnowledgeGraphViewUrl(projectName) : null;

  if (!sessionId) {
    return <p className="text-sm text-muted-foreground">Créez ou sélectionnez un projet pour continuer.</p>;
  }

  const handleSubmit = async (evt: FormEvent) => {
    evt.preventDefault();
    setIsSaving(true);
    setStatus(null);
    try {
      await advanceStep(sessionId, "project_details", {
        notes,
        audience: audience || undefined,
        tone: tone || undefined,
        target_duration: targetDuration,
        voice_instructions: voiceInstructions?.trim() || undefined,
        tts_provider: ttsProvider,
        include_citations: includeCitations,
        source_usage_level: sourceUsageLevel
      });
      setCurrentStep("audio_sources");
      navigate("/step/audio_sources");
    } catch (err) {
      setStatus((err as Error).message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-6">
      {showTranscriptionBlock && (
      <section className="overflow-hidden rounded-[14px] border border-[#E2E8F0] bg-white">
        <div className="flex items-center justify-between gap-6 border-b-[0.8px] border-[#E2E8F0] bg-[#F8FAFC] px-5 py-4">
          <div className="flex min-w-0 flex-col gap-1">
            <div className="inline-flex items-center gap-2">
              <FileText className="h-5 w-5 text-[#0F172B]" />
              <h3 className="text-[20px] font-semibold leading-none text-[#0F172B]">Transcription</h3>
            </div>
            <p className="text-[14px] font-normal leading-none text-[#45556C]">
              {transcriptionSubtitle}
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setCurrentStep("configuration_scenario");
              navigate("/step/configuration_scenario");
            }}
            className="inline-flex h-[38px] shrink-0 items-center gap-1 rounded-xl bg-[#007AFF] px-3 text-sm font-semibold text-white transition-colors hover:bg-[#006ae0]"
          >
            <Plus className="h-4 w-4" />
            <span>Créer un artefact</span>
          </button>
        </div>

        <div className="flex flex-col gap-6 bg-white px-5 py-4">
          <div className="rounded-2xl border border-[#E2E8F0] bg-white p-4">
            <div className="mb-[18px] flex items-center justify-between gap-3">
              <p className="text-[16px] font-semibold leading-none text-[#0F172B]">
                Fichier 1: {firstAudioFile ?? fallbackFileName}
              </p>
              <div className="inline-flex items-center gap-2">
                <a
                  href={projectName ? getProjectTranscriptionBundleUrl(projectName) : "#"}
                  download
                  aria-disabled={!projectName}
                  className="inline-flex h-[38px] w-[38px] items-center justify-center rounded-[10px] border border-[#E2E8F0] bg-white text-[#45556C] transition-colors hover:bg-[#F8FAFC]"
                  aria-label="Télécharger transcription, événements et graphe"
                >
                  <Download className="h-4 w-4" />
                </a>
                <button
                  type="button"
                  onClick={() => setShowTranscriptionBlock(false)}
                  className="inline-flex h-[38px] items-center gap-1 rounded-[10px] border border-[#E2E8F0] bg-[#F8FAFC] px-3 text-sm font-semibold text-[#45556C] transition-colors hover:bg-[#eef2f7] hover:text-[#0F172B]"
                >
                  <X className="h-4 w-4" />
                  <span>Supprimer</span>
                </button>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={togglePlay}
                disabled={!audioSrc}
                className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[#E2E8F0] text-[#0F172B] disabled:opacity-50"
                aria-label={audioPlaying ? "Pause" : "Lecture"}
              >
                {audioPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              </button>
              <div className="flex-1">
                <div
                  role="slider"
                  aria-label="Progression audio"
                  aria-valuemin={0}
                  aria-valuemax={Math.round(audioDuration)}
                  aria-valuenow={Math.round(audioCurrent)}
                  onClick={seekTo}
                  className="h-2 w-full cursor-pointer rounded-full bg-[#E2E8F0]"
                >
                  <div
                    className="h-2 rounded-full bg-[#0F172B]"
                    style={{ width: `${audioProgressPct}%` }}
                  />
                </div>
                <div className="mt-1 flex items-center justify-between text-sm font-normal leading-none text-[#45556C]">
                  <span>{formatClock(audioCurrent)}</span>
                  <span>{formatClock(audioDuration)}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={toggleMute}
                disabled={!audioSrc}
                className="shrink-0 text-[#0F172B] disabled:opacity-50"
                aria-label={audioMuted ? "Réactiver le son" : "Couper le son"}
              >
                {audioMuted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
              </button>
              {audioSrc && (
                <audio
                  ref={audioRef}
                  src={audioSrc}
                  preload="metadata"
                  className="hidden"
                  onPlay={() => setAudioPlaying(true)}
                  onPause={() => setAudioPlaying(false)}
                  onEnded={() => setAudioPlaying(false)}
                  onTimeUpdate={(e) => setAudioCurrent(e.currentTarget.currentTime)}
                  onLoadedMetadata={(e) => setAudioDuration(e.currentTarget.duration || 0)}
                  onVolumeChange={(e) => setAudioMuted(e.currentTarget.muted)}
                />
              )}
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {displayedTags.map((tag, index) => (
              <button
                key={index}
                type="button"
                className="inline-flex h-8 w-[157px] items-center justify-between rounded-full border border-[#E2E8F0] bg-white px-4 py-[6px] text-[14px] font-semibold leading-none text-[#45556C]"
              >
                <span>{tag}</span>
                <ChevronDown className="h-3.5 w-3.5" />
              </button>
            ))}
          </div>

          <div className="flex flex-col gap-[18px]">
            <h4 className="text-[16px] font-semibold leading-none text-[#0F172B]">{transcriptionTitle}</h4>
            <p
              className="text-[14px] font-normal leading-none"
              style={{
                background: "linear-gradient(180deg, #45556C 0%, #F3F4F8 100%)",
                WebkitBackgroundClip: "text",
                backgroundClip: "text",
                color: "transparent",
              }}
            >
              {transcriptionText}
            </p>
          </div>

          <div className="flex items-center justify-end gap-[14px]">
            <button
              type="button"
              onClick={() => setShowTranscriptionBlock(false)}
              className="inline-flex h-[37.6px] items-center gap-3 rounded-full border border-[#E2E8F0] bg-transparent px-3 text-sm font-medium text-[#45556C] transition-colors hover:bg-[#F8FAFC] hover:text-[#0F172B]"
            >
              <X className="h-4 w-4" />
              <span>Fermer</span>
            </button>
            <a
              href={projectName ? getProjectTranscriptionBundleUrl(projectName) : "#"}
              download
              aria-disabled={!projectName}
              className="inline-flex h-[38px] items-center gap-1 rounded-xl border border-[#E2E8F0] bg-white px-3 text-sm font-semibold text-[#45556C] transition-colors hover:bg-[#F8FAFC] hover:text-[#0F172B]"
            >
              <Download className="h-4 w-4" />
              <span>Exporter la transcription</span>
            </a>
          </div>
        </div>
      </section>
      )}

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <article className="overflow-hidden rounded-[14px] border border-[#E2E8F0] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
          <div className="flex items-center gap-6 border-b-[0.8px] border-[#E2E8F0] bg-[#F8FAFC] px-5 py-4">
            <div className="flex min-w-0 flex-col gap-1">
              <div className="inline-flex items-center gap-1">
                <Network className="h-5 w-5 text-[#0F172B]" />
                <h3 className="text-[20px] font-semibold leading-none text-[#0F172B]">{knowledgeGraphTitle}</h3>
              </div>
              <p className="text-[14px] font-normal leading-none text-[#45556C]">
                {knowledgeGraphSubtitle}
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-[14px] bg-white px-5 py-4">
            <div className="relative h-[321px] overflow-hidden rounded-xl border border-[#E2E8F0] bg-white p-2">
              <div className="absolute left-3 top-3 z-10 inline-flex items-center gap-2 rounded-full bg-[#F8FAFC] px-3 py-2 text-[28px] text-[#007AFF]">
                <Sparkles className="h-4 w-4" />
                <span className="text-[14px] font-semibold leading-none text-[#007AFF]">
                  {knowledgeGraphNodeCount > 0 ? knowledgeGraphKeywordCount : keywordsCount} Mots-clés identifiés
                </span>
              </div>
              {knowledgeGraphViewUrl && knowledgeGraphNodeCount > 0 && (
                <a
                  href={knowledgeGraphViewUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="absolute right-3 top-3 z-10 inline-flex h-10 w-10 items-center justify-center rounded-[12px] border border-[#E2E8F0] bg-[#F8FAFC] text-[#45556C] transition-colors hover:bg-white"
                  aria-label="Ouvrir le graphe en plein écran"
                >
                  <Eye className="h-4 w-4" />
                </a>
              )}

              <div className="relative h-full w-full overflow-hidden rounded-[10px] bg-[#F8FAFC]">
                {knowledgeGraphViewUrl && knowledgeGraphNodeCount > 0 ? (
                  <iframe
                    key={knowledgeGraphNodeCount}
                    src={knowledgeGraphViewUrl}
                    title="Knowledge graph"
                    className="h-full w-full border-0"
                  />
                ) : (
                  <>
                    {[
                      "left-[15%] top-[65%]", "left-[32%] top-[56%]", "left-[48%] top-[45%]", "left-[58%] top-[30%]",
                      "left-[68%] top-[58%]", "left-[75%] top-[38%]", "left-[21%] top-[42%]", "left-[41%] top-[24%]",
                      "left-[55%] top-[70%]", "left-[80%] top-[64%]", "left-[27%] top-[70%]", "left-[63%] top-[48%]",
                    ].map((pos, idx) => (
                      <span
                        key={idx}
                        className={`absolute ${pos} h-2 w-2 rounded-full ${
                          idx % 4 === 0
                            ? "bg-[#007AFF]"
                            : idx % 3 === 0
                              ? "bg-[#22C55E]"
                              : idx % 2 === 0
                                ? "bg-[#EF4444]"
                                : "bg-[#F97316]"
                        }`}
                      />
                    ))}
                  </>
                )}
              </div>
            </div>
          </div>
        </article>

        <article className="overflow-hidden rounded-[14px] border border-[#E2E8F0] bg-white shadow-[0_2px_10px_rgba(0,0,0,0.10)]">
          <div className="flex items-center gap-6 border-b-[0.8px] border-[#E2E8F0] bg-[#F8FAFC] px-5 py-4">
            <div className="flex min-w-0 flex-col gap-1">
              <div className="inline-flex items-center gap-1">
                <Sparkles className="h-5 w-5 text-[#0F172B]" />
                <h3 className="text-[20px] font-semibold leading-none text-[#0F172B]">{artifactsTitle}</h3>
              </div>
              <p className="text-[14px] font-normal leading-none text-[#45556C]">
                {artifactsSubtitle}
              </p>
            </div>
          </div>

          <div className="flex h-[405.8px] items-end justify-center bg-white px-5 py-4">
            <button
              type="button"
              className="inline-flex h-[52px] w-[52px] items-center justify-center rounded-[12px] bg-[#007AFF] text-white shadow-sm transition-colors hover:bg-[#006ae0]"
              aria-label="Créer un artefact"
            >
              <Plus className="h-7 w-7" />
            </button>
          </div>
        </article>
      </section>

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Détails du projet</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Contexte, public cible, ton et paramètres vocaux.
          </p>
        </div>
        {profileQuery.isFetching && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" />
            Chargement…
          </div>
        )}
      </div>

      {status && (
        <Alert variant="destructive">
          <AlertDescription>{status}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <Card>
          <CardHeader>
            <CardTitle>Contexte narratif</CardTitle>
            <CardDescription>Décrivez l'histoire à raconter. Les agents IA s'appuieront sur ce texte.</CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={6}
              value={notes}
              onChange={(e) => { setNotes(e.target.value); (window as Window & { __projectNotes?: string }).__projectNotes = e.target.value; }}
              placeholder="Quelle histoire souhaitez-vous raconter ? Quelle période, quel territoire, quels événements ?"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Public & ton narratif</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col gap-1.5">
              <Label>Public cible</Label>
              <Select value={audience} onValueChange={setAudience}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionner…" />
                </SelectTrigger>
                <SelectContent>
                  {audienceOptions.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {formatOptionLabel(opt)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Ton narratif</Label>
              <Select value={tone} onValueChange={setTone}>
                <SelectTrigger>
                  <SelectValue placeholder="Sélectionner…" />
                </SelectTrigger>
                <SelectContent>
                  {toneOptions.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {formatOptionLabel(opt)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Durée audio ciblée</CardTitle>
          </CardHeader>
          <CardContent>
            <Slider
              label="Durée"
              valueLabel={formatDuration(targetDuration)}
              hint={`Entre ${sliderRangeLabel}`}
              min={durationSettings.min}
              max={durationSettings.max}
              step={durationSettings.step}
              value={targetDuration}
              onChange={(e) => setTargetDuration(Number(e.target.value))}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Moteur de synthèse vocale</CardTitle>
            <CardDescription>Choisissez la technologie TTS utilisée pour la narration finale.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex items-center gap-4">
              <span className={ttsProvider !== "elevenlabs" ? "font-semibold text-sm" : "text-sm text-muted-foreground"}>
                Qwen local
              </span>
              <Switch
                checked={ttsProvider === "elevenlabs"}
                onCheckedChange={(checked) => setTtsProvider(checked ? "elevenlabs" : "qwen")}
                aria-label="Basculer entre Qwen local et ElevenLabs"
              />
              <span className={ttsProvider === "elevenlabs" ? "font-semibold text-sm" : "text-sm text-muted-foreground"}>
                ElevenLabs
              </span>
              <Badge variant={ttsProvider === "elevenlabs" ? "default" : "secondary"}>
                {ttsProvider === "elevenlabs" ? "Cloud" : "Local"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              {ttsProvider === "elevenlabs"
                ? "Voix ElevenLabs hébergées — qualité et expressivité maximales."
                : "Synthèse locale Qwen — aucune dépendance cloud, voix générée d'après vos consignes."}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Consignes vocales</CardTitle>
            <CardDescription>Instructions transmises au moteur TTS pour guider le style de narration.</CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              rows={4}
              value={voiceInstructions}
              onChange={(e) => setVoiceInstructions(e.target.value)}
              placeholder="Ex: Use a female narrator, warm and composed, with slight regional accent…"
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sources & citations</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="flex flex-col gap-1.5">
                <Label>Utilisation des sources audio</Label>
                <Select
                  value={sourceUsageLevel}
                  onValueChange={(v) => setSourceUsageLevel(v as "leger" | "modere" | "central")}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="leger">Léger — contexte uniquement</SelectItem>
                    <SelectItem value="modere">Modéré — sourcing équilibré</SelectItem>
                    <SelectItem value="central">Central — élément narratif majeur</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Détermine l'importance des transcriptions dans le récit.
                </p>
              </div>
              <div className="flex flex-col gap-2 justify-center">
                <Label className="flex items-center gap-2 cursor-pointer">
                  <Switch
                    checked={includeCitations}
                    onCheckedChange={setIncludeCitations}
                    id="citations-toggle"
                  />
                  <span>Inclure les citations directes</span>
                </Label>
                <p className="text-xs text-muted-foreground">
                  Autorise le scénariste à citer des extraits des sources.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Separator />

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={isSaving}>
            {isSaving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Save className="mr-2 h-4 w-4" />
            )}
            Sauvegarder & continuer
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
