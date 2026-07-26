import { useEffect, useState, useCallback, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import { load } from "@tauri-apps/plugin-store";
import { listen } from "@tauri-apps/api/event";
import { error } from "@tauri-apps/plugin-log";
import {
  structuredClipboardText,
  type ClipboardPayload,
} from "../utils/clipboardStructure";
import { planTextForTTS, type SpeechSegment } from "../utils/speechPlanner";
import {
  estimateFirstAudioMs,
  estimatedGenerationProgress,
  estimatedRemainingLabel,
  recordFirstAudioSample,
  type FirstAudioContext,
  type FirstAudioSample,
} from "../utils/firstAudioEstimator";
import {
  eventBelongsToRequest,
  statusForTtsEvent,
  type TtsLifecycleEvent,
  type TtsStatus,
} from "../utils/ttsEvents";

// ─── Speed Notches ───────────────────────────────────────────────────────────
// Range: 0.5x – 2.0x in 0.1 increments (16 notches).
// Fixes #12: extends maximum speed well beyond the previous 1.3x cap.
const SPEED_NOTCHES = [
  0.5, 0.6, 0.7, 0.8, 0.9,
  1.0,
  1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0,
] as const;
const DEFAULT_SPEED_INDEX = 5; // 1.0x
const FIRST_AUDIO_HISTORY_KEY = "first-audio-history-v2";
const DEFAULT_BACKEND_ID = "kokoro-pytorch-cpu";

type ReaderSettingsUpdate = {
  skipCodeBlocks?: boolean;
};

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
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white/40">
    <path d="M6 6h12v12H6z" />
  </svg>
);

const CloseIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="w-4 h-4">
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const CopyIcon = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 ml-1.5 inline-block">
    <path d="M16 1H4C2.9 1 2 1.9 2 3V17H4V3H16V1ZM19 5H8C6.9 5 6 5.9 6 7V21C6 22.1 6.9 23 8 23H19C20.1 23 21 22.1 21 21V7C21 5.9 20.1 5 19 5ZM19 21H8V7H19V21Z" />
  </svg>
);

export default function FloatingWidget() {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speedIndex, setSpeedIndex] = useState(DEFAULT_SPEED_INDEX);
  const [status, setStatus] = useState<TtsStatus>("Idle");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [flashKey, setFlashKey] = useState(0); // full widget flash (on hotkey)
  const [subtleFlashKey, setSubtleFlashKey] = useState(0); // tiny dot pulse (on global copy)
  const [generationElapsedMs, setGenerationElapsedMs] = useState(0);
  const [firstAudioContext, setFirstAudioContext] = useState<FirstAudioContext | null>(null);
  const hasEnteredRef = useRef(false);
  const speedIndexRef = useRef(DEFAULT_SPEED_INDEX);
  const storeRef = useRef<Awaited<ReturnType<typeof load>> | null>(null);
  const activeRequestIdRef = useRef<string | null>(null);
  const requestReceivedAtRef = useRef<number | null>(null);
  const firstAudioContextRef = useRef<FirstAudioContext | null>(null);
  const firstAudioHistoryRef = useRef<FirstAudioSample[]>([]);
  const skipCodeBlocksRef = useRef(false);

  const speed = SPEED_NOTCHES[speedIndex];
  const lastSpeechPlan = useRef<SpeechSegment[]>([]);

  // ── Dragging ──
  // ── Load persisted speed ──
  useEffect(() => {
    (async () => {
      const store = await load("settings.json", {
        defaults: {
          "tts-speed-index": DEFAULT_SPEED_INDEX,
          [FIRST_AUDIO_HISTORY_KEY]: [],
        },
        autoSave: true,
      });
      storeRef.current = store;
      const saved = await store.get<number>("tts-speed-index");
      const savedFirstAudioHistory = await store.get<FirstAudioSample[]>(FIRST_AUDIO_HISTORY_KEY);
      const savedSkipCodeBlocks = await store.get<boolean>("skip-code-blocks");
      if (typeof savedSkipCodeBlocks === "boolean") {
        skipCodeBlocksRef.current = savedSkipCodeBlocks;
      }
      if (Array.isArray(savedFirstAudioHistory)) {
        firstAudioHistoryRef.current = savedFirstAudioHistory.filter(
          (sample) => (
            typeof sample === "object"
            && sample !== null
            && typeof sample.backend === "string"
            && typeof sample.voice === "string"
            && typeof sample.firstSegmentChars === "number"
            && typeof sample.durationMs === "number"
          ),
        );
      }
      if (typeof saved === 'number' && saved >= 0 && saved < SPEED_NOTCHES.length) {
        speedIndexRef.current = saved;
        setSpeedIndex(saved);
      } else {
        speedIndexRef.current = DEFAULT_SPEED_INDEX;
        setSpeedIndex(DEFAULT_SPEED_INDEX);
      }
    })();
  }, []);

  useEffect(() => {
    const unlisten = listen<ReaderSettingsUpdate>("settings-updated", (event) => {
      if (typeof event.payload.skipCodeBlocks === "boolean") {
        skipCodeBlocksRef.current = event.payload.skipCodeBlocks;
      }
    });
    return () => { unlisten.then(fn => fn()); };
  }, []);

  // ── Listen for Sidecar Events ──
  useEffect(() => {
    const unlistenLifecycle = listen<TtsLifecycleEvent>("tts-event", (event) => {
      const lifecycle = event.payload;
      if (!eventBelongsToRequest(lifecycle, activeRequestIdRef.current)) return;

      if (lifecycle.event === "request_received") {
        requestReceivedAtRef.current = lifecycle.timestampMs;
      } else if (
        lifecycle.event === "playback_started"
        && requestReceivedAtRef.current !== null
        && firstAudioContextRef.current !== null
      ) {
        const durationMs = lifecycle.timestampMs - requestReceivedAtRef.current;
        const nextHistory = recordFirstAudioSample(
          firstAudioHistoryRef.current,
          durationMs,
          firstAudioContextRef.current,
        );
        firstAudioHistoryRef.current = nextHistory;
        requestReceivedAtRef.current = null;
        void storeRef.current?.set(FIRST_AUDIO_HISTORY_KEY, nextHistory);
      }

      const nextStatus = statusForTtsEvent(lifecycle);
      if (nextStatus) setStatus(nextStatus);

      if (nextStatus === "Idle") {
        activeRequestIdRef.current = null;
        requestReceivedAtRef.current = null;
        setIsPlaying(false);
      } else if (nextStatus === "TTS Error") {
        const msg = typeof lifecycle.data.message === "string"
          ? lifecycle.data.message
          : "Unknown error";
        setErrorMessage(msg);
        activeRequestIdRef.current = null;
        requestReceivedAtRef.current = null;
        setIsPlaying(false);
      }
    });

    // Process-level failures do not belong to a TTS request and retain their
    // legacy channel until the sidecar manager has its own structured protocol.
    const unlistenError = listen<string>("tts-error", (event) => {
      const msg = event.payload || "Unknown error";
      console.error("[Kokoro UI] Sidecar error:", msg);
      setErrorMessage(msg);
      setStatus("TTS Error");
      setIsPlaying(false);
    });

    return () => {
      unlistenLifecycle.then(fn => fn());
      unlistenError.then(fn => fn());
    };
  }, []);

  // ── Persist speed ──
  useEffect(() => {
    storeRef.current?.set("tts-speed-index", speedIndex);
  }, [speedIndex]);

  useEffect(() => {
    if (status !== "Generating") return;
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setGenerationElapsedMs(Date.now() - startedAt);
    }, 100);
    return () => window.clearInterval(timer);
  }, [status]);

  // ── TTS Logic ──
  const runTTS = async (speechPlan: SpeechSegment[]) => {
    try {
      const synthesisSegments = speechPlan
        .filter((segment) => segment.spokenText)
        .map(({ id, kind, spokenText, pauseAfterMs }) => ({
          id,
          kind,
          spokenText,
          pauseAfterMs,
        }));
      if (synthesisSegments.length === 0) return;

      const requestId = crypto.randomUUID();
      activeRequestIdRef.current = requestId;
      requestReceivedAtRef.current = null;
      setGenerationElapsedMs(0);
      setStatus("Generating");
      setIsPlaying(true);
      setErrorMessage(""); // clear any previous error
      
      const store = storeRef.current || await load("settings.json", { defaults: {}, autoSave: true });
      const voice = (await store.get<string>("voice")) || "am_fenrir";
      const volume = (await store.get<number>("volume")) ?? 1.0;
      const estimatorContext = {
        backend: DEFAULT_BACKEND_ID,
        voice,
        firstSegmentChars: synthesisSegments[0].spokenText.length,
      } satisfies FirstAudioContext;
      firstAudioContextRef.current = estimatorContext;
      setFirstAudioContext(estimatorContext);

      await invoke("send_to_tts", { 
        text: synthesisSegments.map((segment) => segment.spokenText).join("\n"),
        speed: speed, 
        voice: voice,
        volume: volume,
        requestId,
        segments: synthesisSegments,
      });
      // Status remains "Generating" until the first audible buffer is reported.
    } catch (err) {
      const msg = String(err);
      error(`[Kokoro UI] Invoke error: ${msg}`);
      setErrorMessage(msg);
      setIsPlaying(false);
      setStatus("TTS Error");
    }
  };

  // ── Listen to Hotkey ──
  useEffect(() => {
    const unlisten = listen("shortcut-triggered", async () => {
      try {
        const clipboardPayload = await invoke<ClipboardPayload>("read_clipboard_payload");
        const clipboardText = structuredClipboardText(clipboardPayload);
        if (clipboardText && clipboardText.trim()) {
          const speechPlan = planTextForTTS(clipboardText, {
            skipCodeBlocks: skipCodeBlocksRef.current,
          });
          lastSpeechPlan.current = speechPlan;

          // Fixes #11: flash the widget to confirm clipboard text received
          setFlashKey((k) => k + 1);
          
          // Smart Positioning: only move to cursor if not already visible
          await invoke("ensure_reader_visible");
          await runTTS(speechPlan);
        }
      } catch (err) {
        error(`[Kokoro UI] Shortcut handler error: ${err}`);
      }
    });

    return () => { unlisten.then(fn => fn()); };
  }, [speed]);

  // ── Listen for Global Clipboard Changes ──
  useEffect(() => {
    const unlisten = listen("global-clipboard-change", () => {
      setSubtleFlashKey((k) => k + 1);
    });
    return () => { unlisten.then(fn => fn()); };
  }, []);

  // ── Speed cycling ──
  const cycleSpeed = useCallback((direction: 1 | -1) => {
    const next = (
      speedIndexRef.current + direction + SPEED_NOTCHES.length
    ) % SPEED_NOTCHES.length;
    speedIndexRef.current = next;
    setSpeedIndex(next);
    if (
      activeRequestIdRef.current
      && (status === "Generating" || status === "Speaking" || status === "Paused")
    ) {
      void invoke("set_tts_speed", {
        requestId: activeRequestIdRef.current,
        speed: SPEED_NOTCHES[next],
      }).catch((err) => error(String(err)));
    }
  }, [status]);

  // ── Scroll-wheel handler ──
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      cycleSpeed(e.deltaY < 0 ? 1 : -1);
    },
    [cycleSpeed]
  );

  // ── Play / Pause / Resume ──
  const handlePlayPause = useCallback(async () => {
    if (status === "Speaking") {
      // If speaking, pause it (Issue #5)
      await invoke("pause_tts", { requestId: activeRequestIdRef.current ?? "" })
        .catch((err) => error(String(err)));
    } else if (status === "Paused") {
      // If paused, resume it
      await invoke("resume_tts", { requestId: activeRequestIdRef.current ?? "" })
        .catch((err) => error(String(err)));
    } else if (status === "Idle" || status === "TTS Error") {
      // If idle, start a fresh run
      if (lastSpeechPlan.current.length > 0) {
        await runTTS(lastSpeechPlan.current);
      }
    }
  }, [isPlaying, status, speed]);

  // ── Stop ──
  const handleStop = useCallback(async () => {
    const requestId = activeRequestIdRef.current;
    if (requestId) {
      await invoke("stop_tts", { requestId }).catch((err) => error(String(err)));
    }
    setIsPlaying(false);
    setStatus("Idle");
  }, []);

  // ── Close ──
  const handleClose = useCallback(async () => {
    const requestId = activeRequestIdRef.current;
    activeRequestIdRef.current = null;
    setIsPlaying(false);
    setStatus("Idle");

    // Hiding the widget must never wait for inference, playback, or a sidecar
    // control request. Fall back to the Rust command if the local window API
    // is unavailable during teardown.
    await getCurrentWebviewWindow().hide().catch(async () => {
      await invoke("hide_reader_window");
    }).catch((err) => error(String(err)));

    if (requestId) {
      void invoke("stop_tts", { requestId }).catch((err) => error(String(err)));
    }
  }, []);

  const statusColor = 
    status === 'Speaking' ? 'text-[#8AB4F8]' : 
    status === 'Generating' ? 'text-yellow-400' : 
    status === 'Paused' ? 'text-[#8AB4F8]/60' : 
    status === 'TTS Error' ? 'text-red-400' : 
    'text-white/20';

  const firstAudioEstimateMs = estimateFirstAudioMs(
    firstAudioHistoryRef.current,
    firstAudioContext,
  );
  const generationProgress = estimatedGenerationProgress(
    generationElapsedMs,
    firstAudioEstimateMs,
  );
  const generationRemaining = estimatedRemainingLabel(
    generationElapsedMs,
    firstAudioEstimateMs,
  );
  
  // Only play the entrance pop once
  useEffect(() => {
    hasEnteredRef.current = true;
  }, []);

  return (
    <div className="window-wrapper" data-tauri-drag-region>
      {/* "Copied" Toast (Issue #11) */}
      {subtleFlashKey > 0 && (
        <div 
          key={subtleFlashKey}
          className="copied-toast animate-toast-in-out absolute pointer-events-none flex items-center"
        >
          clipboard copied
          <CopyIcon />
        </div>
      )}

      <div
        key={flashKey}
        className={`content-container rounded-full flex items-center gap-1.5 px-2 py-1.5 cursor-move relative transition-smooth ${flashKey > 0 ? 'animate-juicy-flash' : (!hasEnteredRef.current ? 'animate-pop' : '')}`}
        data-tauri-drag-region
      >
        {/* Play / Pause */}
        <button
          onClick={handlePlayPause}
          onMouseDown={(e) => e.stopPropagation()}
          title={status === "Speaking" ? "Pause" : "Read Aloud"}
          className="
            w-9 h-9 rounded-full flex items-center justify-center shrink-0
            bg-[#8AB4F8] hover:bg-[#AECBFA]
            active:scale-95 transition-smooth
            text-[#202124] shadow-md cursor-default
          "
        >
          {status === "Speaking" ? <PauseIcon /> : <PlayIcon />}
        </button>

        {/* Stop Button */}
        <button
          onClick={handleStop}
          onMouseDown={(e) => e.stopPropagation()}
          title="Stop & Reset"
          className="
            w-7 h-7 rounded-full flex items-center justify-center shrink-0
            bg-white/5 hover:bg-white/10
            active:scale-95 transition-smooth
            cursor-default
          "
        >
          <StopIcon />
        </button>

        {/* Status Hub */}
        <div className="flex flex-col px-1 min-w-[72px] pointer-events-none" data-tauri-drag-region>
          <span
            className={`text-[8px] font-black uppercase tracking-[0.15em] leading-none transition-smooth ${statusColor} ${status === 'TTS Error' && errorMessage ? 'pointer-events-auto cursor-help' : ''}`}
            title={status === 'TTS Error' && errorMessage ? errorMessage : undefined}
            data-tauri-drag-region
          >
            {status}
          </span>
          {status === "Generating" && (
            <span className="mt-1 text-[8px] leading-none text-white/35 tabular-nums">
              {generationRemaining ?? "estimating"}
            </span>
          )}
        </div>

        {/* Speed Bubble */}
        <button
          onClick={() => cycleSpeed(1)}
          onWheel={handleWheel}
          onMouseDown={(e) => e.stopPropagation()}
          title={`Speed: ${speed}x (Scroll or click)`}
          className="
            w-9 h-9 rounded-full flex items-center justify-center shrink-0
            bg-white/5 hover:bg-white/10
            active:scale-95 transition-smooth
            text-[11px] font-bold text-white/90
            tabular-nums cursor-default
          "
        >
          {speed.toFixed(1)}x
        </button>

        {/* Close */}
        <button
          type="button"
          onClick={handleClose}
          onPointerDown={(e) => e.stopPropagation()}
          title="Close"
          className="
            w-7 h-7 rounded-full flex items-center justify-center shrink-0
            bg-white/5 hover:bg-red-500/20
            active:scale-95 transition-smooth
            text-white/30 hover:text-red-400 cursor-default
          "
        >
          <CloseIcon />
        </button>

        {status === "Generating" && (
          <div className="generation-progress-track" aria-hidden="true">
            {generationProgress === null ? (
              <div className="generation-progress-indeterminate" />
            ) : (
              <div
                className="generation-progress-value"
                style={{ transform: `scaleX(${generationProgress})` }}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
