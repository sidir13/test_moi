import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE ?? "";
export const API_BASE_URL = baseURL;

const api = axios.create({
  baseURL
});

export async function fetchSteps() {
  const { data } = await api.get("/steps");
  return data;
}

export async function fetchStepConfig(stepId: string) {
  const { data } = await api.get(`/steps/${stepId}`);
  return data;
}

export type ProjectSummary = {
  name: string;
  scenario_target: number;
  finalized_at?: string;
  final_audio?: {
    path: string;
    generated_at?: string;
    language?: string;
  } | null;
  final_slideshow?: {
    path: string;
    created_at?: string;
  } | null;
};

export type PreferenceOptions = {
  tone_options: string[];
  audience_options: string[];
  duration: {
    min: number;
    max: number;
    step: number;
    default: number;
  };
};

export type ProjectProfile = {
  name: string;
  scenario_target: number;
  project_notes?: string;
  voice_instructions?: string;
  voice_instructions_source?: string;
  allowed_websites?: string[];
  audience?: string;
  tone?: string;
  target_duration?: number;
  tts_provider?: "qwen" | "elevenlabs";
  tts_voice_id?: string | null;
  include_citations?: boolean;
  source_usage_level?: "leger" | "modere" | "central";
  preference_options?: PreferenceOptions;
  last_scenarios?: Array<Record<string, unknown>>;
  last_scenarios_generated_at?: string;
  final_scenario?: Record<string, unknown>;
  final_audio?: {
    path: string;
    generated_at?: string;
    language?: string;
    sample_rate?: number;
  };
  final_slideshow?: {
    path: string;
    created_at?: string;
  };
  audio_selection?: AudioSelection;
};

export type AudioSelection = {
  voices: string[];
  backgrounds: string[];
  tts_voice_id?: string | null;
  tts_provider?: string;
};

export async function fetchProjects() {
  const { data } = await api.get("/projects");
  return data.projects as ProjectSummary[];
}

export async function fetchProjectProfile(projectName: string) {
  const { data } = await api.get(`/projects/${encodeURIComponent(projectName)}`);
  return data as ProjectProfile;
}

export async function createProject(payload: { name: string; description?: string; scenario_target: number }) {
  const { data } = await api.post("/projects", payload);
  return data;
}

export async function createSession(projectName: string, initialStep = "project_selection", scenarioTarget?: number) {
  const { data } = await api.post("/sessions", {
    project_name: projectName,
    initial_step: initialStep,
    scenario_target: scenarioTarget
  });
  return data;
}

export async function advanceStep(sessionId: string, stepId: string, payload: Record<string, unknown>) {
  const { data } = await api.post(`/sessions/${sessionId}/step`, {
    step_id: stepId,
    payload
  });
  return data;
}

export async function uploadAudio(projectName: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(`/projects/${projectName}/audio`, form, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return data;
}

export type BackgroundSound = {
  path: string;
  name: string;
  preview: string;
  category?: string;
  tags?: string[];
  description?: string;
  duration?: number;
};

export async function fetchBackgroundSounds(keyword?: string) {
  const { data } = await api.get("/background-sounds", {
    params: keyword ? { keyword } : undefined
  });
  return data.files as BackgroundSound[];
}

export async function uploadBackgroundSound(title: string, file: File) {
  const form = new FormData();
  form.append("title", title);
  form.append("file", file);
  const { data } = await api.post("/background-sounds/upload", form, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return data;
}

export type LlmModelInfo = {
  id: string;
  openrouterId: string;
  label: string;
  provider: string;
  description: string;
};

export async function fetchModels(): Promise<LlmModelInfo[]> {
  const { data } = await api.get("/models");
  return data.models as LlmModelInfo[];
}

export async function generateScenarios(
  sessionId: string,
  prompt: string,
  scenarioTarget?: number,
  mode: "simple" | "expert" = "simple",
  modelId?: string
) {
  const { data } = await api.post("/scenarios/generate", {
    session_id: sessionId,
    prompt,
    mode,
    scenario_target: scenarioTarget,
    model_id: modelId || undefined
  });
  return data;
}

export async function fetchProjectAudio(projectName: string) {
  const { data } = await api.get(`/projects/${projectName}/audio`);
  return data.files as string[];
}

export async function fetchAudioSelection(sessionId: string) {
  const { data } = await api.get(`/sessions/${sessionId}/audio-selection`);
  return data as AudioSelection;
}

export async function saveAudioSelection(sessionId: string, payload: AudioSelection & { project_name: string }) {
  const { data } = await api.post(`/sessions/${sessionId}/audio-selection`, payload);
  return data as AudioSelection;
}

export async function fetchScenarios(sessionId: string) {
  const { data } = await api.get(`/sessions/${sessionId}/scenarios`);
  return data.scenarios as Array<Record<string, unknown>>;
}

export type ScenarioProgressStep = {
  label: string;
  message?: string;
  status: "pending" | "running" | "done" | "error";
};

export async function selectScenario(sessionId: string, scenario: Record<string, unknown>) {
  const { data } = await api.post(`/sessions/${sessionId}/scenario-selection`, {
    scenario
  });
  return data;
}

export async function fetchSelectedScenario(sessionId: string) {
  const { data } = await api.get(`/sessions/${sessionId}/scenario-selection`);
  return data.scenario as Record<string, unknown> | undefined;
}

export async function fetchScenarioProgress(sessionId: string) {
  const { data } = await api.get(`/sessions/${sessionId}/scenario-progress`);
  return (data.steps ?? []) as ScenarioProgressStep[];
}

export type ScenarioAudioMetadata = {
  status?: "pending" | "running" | "done" | "failed";
  job_id?: string;
  path?: string;
  language?: string;
  sample_rate?: number;
  generated_at?: string;
  text_length?: number;
  error?: string;
  requested_at?: string;
  started_at?: string;
  finished_at?: string;
  tts_provider?: string;
  backgrounds_applied?: number;
  background_tracks_requested?: number;
  voice_only_path?: string;
  background_plan?: Array<{
    background: string;
    start_seconds: number;
    duration_seconds: number;
    note?: string | null;
  }>;
};

export async function fetchScenarioAudio(sessionId: string) {
  try {
    const { data } = await api.get(`/sessions/${sessionId}/scenario-audio`);
    return data as ScenarioAudioMetadata;
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 404) {
      return null;
    }
    throw err;
  }
}

export async function synthesizeScenarioAudio(
  sessionId: string,
  payload?: { text?: string; language?: string }
) {
  const { data } = await api.post(`/sessions/${sessionId}/scenario-audio`, payload ?? {});
  return data as ScenarioAudioMetadata;
}

export function getScenarioAudioUrl(sessionId: string) {
  const prefix = (API_BASE_URL || "").replace(/\/$/, "");
  const base = prefix.length > 0 ? prefix : "";
  return `${base}/sessions/${sessionId}/scenario-audio/file`;
}

export type ScenarioImage = {
  id: string;
  filename: string;
  original_name?: string;
  uploaded_at?: string;
  download_url: string;
};

export async function fetchScenarioImages(sessionId: string) {
  const { data } = await api.get(`/sessions/${sessionId}/scenario-images`);
  return data.images as ScenarioImage[];
}

export async function uploadScenarioImage(sessionId: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(`/sessions/${sessionId}/scenario-images`, form, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  return data.image as ScenarioImage;
}

export async function deleteScenarioImage(sessionId: string, imageId: string) {
  await api.delete(`/sessions/${sessionId}/scenario-images/${imageId}`);
}

export async function reorderScenarioImages(sessionId: string, order: string[]) {
  const { data } = await api.post(`/sessions/${sessionId}/scenario-images/reorder`, { order });
  return data.images as ScenarioImage[];
}

export type SlideshowMetadata = {
  status: string;
  path: string;
  created_at?: string;
  image_count?: number;
};

export async function fetchSlideshow(sessionId: string) {
  try {
    const { data } = await api.get(`/sessions/${sessionId}/slideshow`);
    return data as SlideshowMetadata;
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 404) {
      return null;
    }
    throw err;
  }
}

export async function createSlideshow(sessionId: string) {
  const { data } = await api.post(`/sessions/${sessionId}/slideshow`);
  return data as SlideshowMetadata;
}

export function getScenarioSlideshowUrl(sessionId: string) {
  const prefix = (API_BASE_URL || "").replace(/\/$/, "");
  const base = prefix.length > 0 ? prefix : "";
  return `${base}/sessions/${sessionId}/slideshow/file`;
}

export function getProjectFinalAudioUrl(projectName: string) {
  const prefix = (API_BASE_URL || "").replace(/\/$/, "");
  const base = prefix.length > 0 ? prefix : "";
  const encoded = encodeURIComponent(projectName);
  return `${base}/projects/${encoded}/final-audio`;
}

export function getProjectFinalVideoUrl(projectName: string) {
  const prefix = (API_BASE_URL || "").replace(/\/$/, "");
  const base = prefix.length > 0 ? prefix : "";
  const encoded = encodeURIComponent(projectName);
  return `${base}/projects/${encoded}/slideshow`;
}

export function getWsBaseUrl() {
  const target = baseURL || window.location.origin;
  if (target.startsWith("https")) return target.replace("https", "wss");
  if (target.startsWith("http")) return target.replace("http", "ws");
  return `ws://${target}`;
}
