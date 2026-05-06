import { useEffect, useRef } from "react";
import WaveSurfer from "wavesurfer.js";
import { useSessionStore } from "@/hooks/useSessionStore";
import { getScenarioAudioUrl } from "@/api/client";
import { AudioLines } from "lucide-react";

export function WaveformPanel() {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const { sessionId } = useSessionStore();

  useEffect(() => {
    if (!containerRef.current) return;
    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#cbd5e1",
      progressColor: "#2563eb",
      height: 40,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      interact: false,
      normalize: true
    });
    wavesurferRef.current = ws;
    return () => ws.destroy();
  }, []);

  useEffect(() => {
    if (!sessionId || !wavesurferRef.current) return;
    const url = getScenarioAudioUrl(sessionId);
    wavesurferRef.current.load(url).catch(() => {});
  }, [sessionId]);

  return (
    <div className="flex items-center gap-3 px-6 py-2">
      <AudioLines className="h-4 w-4 shrink-0 text-muted-foreground" />
      <div ref={containerRef} className="flex-1" />
    </div>
  );
}
