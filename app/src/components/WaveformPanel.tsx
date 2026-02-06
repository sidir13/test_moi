import { useEffect, useRef } from "react";
import WaveSurfer from "wavesurfer.js";

export function WaveformPanel() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const waveRef = useRef<WaveSurfer | null>(null);

  useEffect(() => {
    if (!containerRef.current || waveRef.current) return;
    waveRef.current = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#5f6",
      progressColor: "#1c1",
      cursorColor: "#111",
      height: 60
    });
    return () => {
      waveRef.current?.destroy();
      waveRef.current = null;
    };
  }, []);

  return (
    <div className="waveform">
      <strong>Timeline audio</strong>
      <div ref={containerRef} />
    </div>
  );
}
