import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? ""
});

export async function fetchSteps() {
  const { data } = await api.get("/steps");
  return data;
}

export async function fetchStepConfig(stepId: string) {
  const { data } = await api.get(`/steps/${stepId}`);
  return data;
}

export async function sendChatMessage(sessionId: string, message: string) {
  return api.post(`/sessions/${sessionId}/chat`, { message });
}
