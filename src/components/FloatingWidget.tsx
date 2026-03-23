import { useEffect, useState, useCallback, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { load } from "@tauri-apps/plugin-store";

// ─── Speed Notches ─────────────────────────────────────────────────────────
const SPEED_NOTCHES = [1, 1.25, 1.5, 1.75, 2, 0.5, 0.75] as const;

// ─── Icons (inline SVGs for zero-dependency icons) ─────────────────────────
const PlayIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
    <path d="M8 5.14v14l11-7-11-7z" />
  </svg>
);

const PauseIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
  </svg>
);

const StopIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4">
    <path d="M6 6h12v12H6z" />
  </svg>
);

export default function FloatingWidget() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speedIndex, setSpeedIndex] = useState(0);
  const storeRef = useRef<Awaited<ReturnType<typeof load>> | null>(null);

  const speed = SPEED_NOTCHES[speedIndex];

  // ── Load persisted speed on mount ──
  useEffect(() => {
    (async () => {
      const store = await load("settings.json", { defaults: {}, autoSave: true });
      storeRef.current = store;
      const saved = await store.get<number>("tts-speed-index");
      if (saved !== null && saved !== undefined && saved >= 0 && saved < SPEED_NOTCHES.length) {
        setSpeedIndex(saved);
      }
    })();
  }, []);

  // ── Persist speed whenever it changes ──
  useEffect(() => {
    storeRef.current?.set("tts-speed-index", speedIndex);
  }, [speedIndex]);

  // ── Speed cycling ──
  const cycleSpeed = useCallback((direction: 1 | -1) => {
    setSpeedIndex((prev) => {
      const next = (prev + direction + SPEED_NOTCHES.length) % SPEED_NOTCHES.length;
      return next;
    });
  }, []);

  // ── Scroll-wheel handler ──
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      cycleSpeed(e.deltaY < 0 ? 1 : -1);
    },
    [cycleSpeed]
  );

  // ── Play / Pause ──
  const handlePlayPause = useCallback(async () => {
    if (isPlaying) {
      // Pause — just stop audio for MVP (no pause/resume on sidecar)
      await invoke("stop_tts").catch(console.error);
      setIsPlaying(false);
    } else {
      setIsPlaying(true);
      // TTS invocation is triggered by the shortcut handler on the Rust side
      // This button is for pause/resume of an in-progress read
    }
  }, [isPlaying]);

  // ── Stop ──
  const handleStop = useCallback(async () => {
    await invoke("stop_tts").catch(console.error);
    setIsPlaying(false);
  }, []);

  return (
    <div className="h-full flex items-center justify-center p-1" data-tauri-drag-region>
      <div className="glass rounded-2xl flex items-center gap-1 px-2 py-1.5 animate-pop">
        {/* Play / Pause */}
        <button
          onClick={handlePlayPause}
          title={isPlaying ? "Pause" : "Read Aloud"}
          className="
            w-10 h-10 rounded-xl flex items-center justify-center
            bg-gradient-to-br from-indigo-500 to-purple-600
            hover:from-indigo-400 hover:to-purple-500
            active:scale-95 transition-smooth
            text-white shadow-lg shadow-indigo-500/30
          "
        >
          {isPlaying ? <PauseIcon /> : <PlayIcon />}
        </button>

        {/* Stop */}
        <button
          onClick={handleStop}
          title="Stop"
          className="
            w-8 h-8 rounded-lg flex items-center justify-center
            bg-white/10 hover:bg-red-500/80
            active:scale-95 transition-smooth
            text-white/70 hover:text-white
          "
        >
          <StopIcon />
        </button>

        {/* Speed Bubble */}
        <button
          onClick={() => cycleSpeed(1)}
          onWheel={handleWheel}
          title={`Speed: ${speed}x (click or scroll to change)`}
          className="
            w-10 h-10 rounded-full flex items-center justify-center
            bg-white/10 hover:bg-white/20
            active:scale-95 transition-smooth
            text-xs font-bold text-white/90
            tabular-nums select-none cursor-pointer
            border border-white/10
          "
        >
          {speed}x
        </button>
      </div>
    </div>
  );
}
