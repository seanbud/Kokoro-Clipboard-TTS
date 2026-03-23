import { useEffect, useState, useCallback, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { load } from "@tauri-apps/plugin-store";
import { listen } from "@tauri-apps/api/event";
import { readText } from "@tauri-apps/plugin-clipboard-manager";
import { cleanTextForTTS } from "../utils/textCleaner";

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
  const lastAnalyzedText = useRef<string>("");

  // ── Load persisted speed on mount ──
  useEffect(() => {
    (async () => {
      console.log("[Kokoro UI] Loading preferences...");
      const store = await load("settings.json", { defaults: {}, autoSave: true });
      storeRef.current = store;
      const saved = await store.get<number>("tts-speed-index");
      if (saved !== null && saved !== undefined && saved >= 0 && saved < SPEED_NOTCHES.length) {
        setSpeedIndex(saved);
        console.log(`[Kokoro UI] Restored speed setting: ${SPEED_NOTCHES[saved]}x`);
      }
    })();
  }, []);

  // ── Persist speed whenever it changes ──
  useEffect(() => {
    storeRef.current?.set("tts-speed-index", speedIndex);
  }, [speedIndex]);

  // ── Listen to Hotkey ──
  useEffect(() => {
    const unlisten = listen("shortcut-triggered", async () => {
      try {
        console.log("[Kokoro UI] ------------- HOTKEY TRIGGERED -------------");
        console.log("[Kokoro UI] Reading clipboard...");
        const clipboardText = await readText();
        console.log(`[Kokoro UI] Captured text length: ${clipboardText?.length || 0} chars`);

        if (clipboardText && clipboardText.trim()) {
          const cleaned = cleanTextForTTS(clipboardText);
          console.log("[Kokoro UI] Cleaned text snippet:", cleaned.substring(0, 60), "...");
          
          lastAnalyzedText.current = cleaned;

          console.log("[Kokoro UI] Showing reader UI window...");
          await invoke("move_reader_window", { x: 100, y: 100 });
          
          console.log(`[Kokoro UI] Forwarding to sidecar... (Speed: ${speed})`);
          setIsPlaying(true);
          
          await invoke("send_to_tts", { text: cleaned, speed: speed, voice: "am_fenrir" });
          console.log("[Kokoro UI] Request dispatched to sidecar successfully.");
        } else {
          console.log("[Kokoro UI] Ignored: Clipboard is empty or contains non-text data.");
        }
      } catch (err) {
        console.error("[Kokoro UI] Shortcut handler error:", err);
      }
    });

    return () => { unlisten.then(fn => fn()); };
  }, [speed]);

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
    console.log(`[Kokoro UI] ⏯️ Play/Pause clicked. User wants to ${isPlaying ? 'PAUSE' : 'PLAY'}`);
    if (isPlaying) {
      console.log("[Kokoro UI] Invoking stop_tts to halt audio...");
      await invoke("stop_tts").catch(console.error);
      setIsPlaying(false);
    } else {
      if (lastAnalyzedText.current) {
        console.log("[Kokoro UI] Re-reading text from memory...");
        setIsPlaying(true);
        await invoke("send_to_tts", { text: lastAnalyzedText.current, speed: speed, voice: "am_fenrir" });
      } else {
        console.log("[Kokoro UI] Warning: No text in memory, cannot resume playback. Waiting for shortcut trigger!");
      }
    }
  }, [isPlaying, speed]);

  // ── Stop ──
  const handleStop = useCallback(async () => {
    console.log("[Kokoro UI] ⏹️ Stop clicked. Halting audio completely.");
    await invoke("stop_tts").catch(console.error);
    setIsPlaying(false);
  }, []);

  return (
    <div className="h-full flex items-center justify-center p-1" data-tauri-drag-region>
      <div className="surface shadow-2xl rounded-full flex items-center gap-1.5 px-2 py-1.5 animate-pop">
        {/* Play / Pause */}
        <button
          onClick={handlePlayPause}
          title={isPlaying ? "Pause" : "Read Aloud"}
          className="
            w-10 h-10 rounded-full flex items-center justify-center
            bg-[#8AB4F8] hover:bg-[#AECBFA]
            active:scale-95 transition-smooth
            text-[#202124] shadow-md
          "
        >
          {isPlaying ? <PauseIcon /> : <PlayIcon />}
        </button>

        {/* Stop */}
        <button
          onClick={handleStop}
          title="Stop"
          className="
            w-8 h-8 rounded-full flex items-center justify-center
            bg-white/5 hover:bg-red-500/20
            active:scale-95 transition-smooth
            text-white/60 hover:text-red-400
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
            min-w-[44px] h-10 px-2.5 rounded-full flex items-center justify-center
            bg-white/5 hover:bg-white/10
            active:scale-95 transition-smooth
            text-[13px] font-semibold text-white/80
            tabular-nums select-none cursor-pointer
            border border-white/5
          "
        >
          {speed}x
        </button>
      </div>
    </div>
  );
}
