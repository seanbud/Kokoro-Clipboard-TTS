import { useEffect, useState, useCallback, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { load } from "@tauri-apps/plugin-store";
import { listen } from "@tauri-apps/api/event";
import { readText } from "@tauri-apps/plugin-clipboard-manager";
import { error } from "@tauri-apps/plugin-log";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import { cleanTextForTTS } from "../utils/textCleaner";

// ─── Speed Notches (Reworked as requested) ──────────────────────────────────
const SPEED_NOTCHES = [1.0, 1.1, 1.2, 1.3] as const;

// ─── Icons ──────────────────────────────────────────────────────────────────
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

const CloseIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-4 h-4">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

type Status = "Idle" | "Processing" | "Speaking";

export default function FloatingWidget() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speedIndex, setSpeedIndex] = useState(0); // 1.0x default
  const [status, setStatus] = useState<Status>("Idle");
  const storeRef = useRef<Awaited<ReturnType<typeof load>> | null>(null);

  const speed = SPEED_NOTCHES[speedIndex];
  const lastAnalyzedText = useRef<string>("");

  // ── Dragging ──
  const handleDrag = () => {
    getCurrentWebviewWindow().startDragging();
  };

  // ── Load persisted speed on mount ──
  useEffect(() => {
    (async () => {
      const store = await load("settings.json", { defaults: { "tts-speed-index": 0 }, autoSave: true });
      storeRef.current = store;
      const saved = await store.get<number>("tts-speed-index");
      if (typeof saved === 'number' && saved >= 0 && saved < SPEED_NOTCHES.length) {
        setSpeedIndex(saved);
      } else {
        setSpeedIndex(0);
      }
    })();
  }, []);

  // ── Persist speed whenever it changes ──
  useEffect(() => {
    storeRef.current?.set("tts-speed-index", speedIndex);
  }, [speedIndex]);

  // ── TTS Logic ──
  const runTTS = async (text: string) => {
    try {
      setStatus("Processing");
      setIsPlaying(true);
      
      const store = storeRef.current || await load("settings.json", { defaults: {}, autoSave: true });
      const voice = (await store.get<string>("voice")) || "am_fenrir";
      const volume = (await store.get<number>("volume")) ?? 1.0;

      const res = await invoke<string>("send_to_tts", { 
        text, 
        speed: speed, 
        voice: voice,
        volume: volume 
      });

      if (res === "ok") {
        setStatus("Speaking");
      }
    } catch (err) {
      error(`[Kokoro UI] TTS error: ${err}`);
      setIsPlaying(false);
      setStatus("Idle");
    }
  };

  // ── Listen to Hotkey ──
  useEffect(() => {
    const unlisten = listen("shortcut-triggered", async () => {
      try {
        const clipboardText = await readText();
        if (clipboardText && clipboardText.trim()) {
          const cleaned = cleanTextForTTS(clipboardText);
          lastAnalyzedText.current = cleaned;
          await invoke("move_reader_window", { x: 100, y: 100 });
          await runTTS(cleaned);
        }
      } catch (err) {
        error(`[Kokoro UI] Shortcut handler error: ${err}`);
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
    if (isPlaying) {
      await invoke("stop_tts").catch((err) => error(String(err)));
      setIsPlaying(false);
      setStatus("Idle");
    } else {
      if (lastAnalyzedText.current) {
        await runTTS(lastAnalyzedText.current);
      }
    }
  }, [isPlaying, speed]);

  // ── Stop ──
  const handleStop = useCallback(async () => {
    await invoke("stop_tts").catch((err) => error(String(err)));
    setIsPlaying(false);
    setStatus("Idle");
  }, []);

  // ── Close ──
  const handleClose = useCallback(async () => {
    await handleStop();
    await invoke("hide_reader_window").catch((err) => error(String(err)));
  }, [handleStop]);

  const statusColor = status === 'Speaking' ? 'text-green-400' : 
    status === 'Processing' ? 'text-yellow-400 animate-pulse' : 
    'text-white/40';

  return (
    <div className="h-full flex items-center justify-center p-1 select-none" onMouseDown={handleDrag}>
      <div 
        className="surface shadow-2xl rounded-full flex items-center gap-1.5 px-2 py-1.5 animate-pop border border-white/10 cursor-move"
      >
        {/* Play / Pause */}
        <button
          onClick={handlePlayPause}
          onMouseDown={(e) => e.stopPropagation()}
          title={isPlaying ? "Pause" : "Read Aloud"}
          className="
            w-10 h-10 rounded-full flex items-center justify-center
            bg-[#8AB4F8] hover:bg-[#AECBFA]
            active:scale-95 transition-smooth
            text-[#202124] shadow-md cursor-default
          "
        >
          {isPlaying ? <PauseIcon /> : <PlayIcon />}
        </button>

        {/* Status Indicator */}
        <div className="flex flex-col px-1 min-w-[50px] pointer-events-none">
          <span className="text-[9px] font-bold text-white/20 uppercase tracking-widest leading-none mb-0.5">
            {status}
          </span>
        </div>

        {/* Speed Bubble */}
        <button
          onClick={() => cycleSpeed(1)}
          onWheel={handleWheel}
          onMouseDown={(e) => e.stopPropagation()}
          title={`Speed: ${speed}x`}
          className="
            min-w-[40px] h-10 px-2 rounded-full flex items-center justify-center
            bg-white/5 hover:bg-white/10
            active:scale-95 transition-smooth
            text-[12px] font-semibold text-white/80
            tabular-nums cursor-default
            border border-white/5
          "
        >
          {speed}x
        </button>

        {/* Close Button (X) */}
        <button
          onClick={handleClose}
          onMouseDown={(e) => e.stopPropagation()}
          title="Close"
          className="
            w-8 h-8 rounded-full flex items-center justify-center
            bg-white/5 hover:bg-red-500/20
            active:scale-95 transition-smooth
            text-white/30 hover:text-red-400 cursor-default
          "
        >
          <CloseIcon />
        </button>
      </div>
    </div>
  );
}
