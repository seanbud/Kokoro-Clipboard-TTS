import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWebviewWindow, getAllWebviewWindows } from "@tauri-apps/api/webviewWindow";
import { load } from "@tauri-apps/plugin-store";
import { error } from "@tauri-apps/plugin-log";
import { openPath, revealItemInDir } from "@tauri-apps/plugin-opener";
import icon from "../assets/icon.png";

export default function Splash() {
  const [status, setStatus] = useState("Initializing...");
  const [dots, setDots] = useState("");
  const [logPath, setLogPath] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Animated dots for loading states
  useEffect(() => {
    const timer = setInterval(() => {
      setDots((d) => (d.length >= 3 ? "" : d + "."));
    }, 500);
    return () => clearInterval(timer);
  }, []);

  // Fetch and store the log path when an error occurs (called at most once)
  const handleEngineError = async () => {
    if (logPath) return; // already fetched
    try {
      const path = await invoke<string>("get_sidecar_log_path");
      if (path) setLogPath(path);
    } catch {
      // non-fatal – just won't show log path
    }
  };

  // ── Main startup orchestration ──
  // Order matters:
  //   1. Register the event listener FIRST (so we never miss events)
  //   2. Then invoke start_sidecar (which emits "starting" and later "ready")
  //   3. Also poll initial status as a fallback
  useEffect(() => {
    let active = true;
    let readyHandled = false; // Prevent double-fire from event + poller

    const onReady = () => {
      if (readyHandled || !active) return;
      readyHandled = true;
      setStatus("Ready!");
      setTimeout(() => { if (active) handleReady(); }, 1800);
    };

    // Step 1: Register event listener BEFORE starting sidecar
    const unlisten = listen<string>("sidecar-status", (event) => {
      if (!active) return;
      const s = event.payload;
      console.log("[Splash] sidecar-status event:", s);
      if (s === "ready") {
        onReady();
      } else if (s === "starting") {
        setStatus("Starting TTS Engine");
      } else if (s.startsWith("error")) {
        setStatus("Engine Error");
        handleEngineError();
      }
    });

    // Step 2: Start the sidecar AFTER listener is registered
    invoke("start_sidecar").catch((e) => {
      console.error("[Splash] Failed to start sidecar:", e);
      if (active) {
        setStatus("Engine Error");
        handleEngineError();
      }
    });

    // Step 3: Fallback — poll initial status in case events were missed
    const pollInterval = setInterval(() => {
      if (!active || readyHandled) return;
      invoke<string>("get_sidecar_status").then((s) => {
        if (!active || readyHandled) return;
        if (s === "ready") {
          clearInterval(pollInterval);
          onReady();
        } else if (s === "starting") {
          setStatus("Starting TTS Engine");
        }
      });
    }, 1000);

    return () => {
      active = false;
      clearInterval(pollInterval);
      unlisten.then((fn) => fn());
    };
  }, []);

  // ── Handle the "Ready" transition ──
  const handleReady = async () => {
    try {
      const store = await load("settings.json", { defaults: {}, autoSave: false });
      const done = await store.get<boolean>("first-run-done");

      if (!done) {
        const windows = await getAllWebviewWindows();
        const tutWin = windows.find(w => w.label === "tutorial");
        if (tutWin) {
          await tutWin.show();
          await tutWin.setFocus();
        }
      }

      const win = getCurrentWebviewWindow();
      await win.close().catch(() => win.destroy());
    } catch (err) {
      error(`[Splash] Ready handler failed: ${err}`);
      getCurrentWebviewWindow().destroy().catch(() => {});
    }
  };

  // ── Log path helpers ──
  const handleCopyPath = () => {
    if (!logPath) return;
    navigator.clipboard.writeText(logPath).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleOpenFolder = async () => {
    if (!logPath) return;
    try {
      // revealItemInDir opens the folder and selects/highlights the log file
      await revealItemInDir(logPath);
    } catch {
      // Fallback: open the parent directory
      const sepIdx = Math.max(logPath.lastIndexOf("/"), logPath.lastIndexOf("\\"));
      if (sepIdx > 0) {
        const logDir = logPath.substring(0, sepIdx);
        try {
          await openPath(logDir);
        } catch {
          handleCopyPath();
        }
      } else {
        handleCopyPath();
      }
    }
  };

  const isError = status.includes("Error");

  return (
    <div className="window-wrapper" data-tauri-drag-region>
      <div 
        className="content-container w-[420px] h-[320px] flex items-center justify-center select-none cursor-move group" 
        data-tauri-drag-region
      >
        {/* Close Button */}
        <button
          onClick={() => {
            console.log("[Splash] Manual close clicked");
            getCurrentWebviewWindow().destroy();
          }}
          onMouseDown={(e) => {
            e.stopPropagation();
          }}
          className="
            absolute top-4 right-4 w-7 h-7 rounded-full 
            flex items-center justify-center 
            bg-white/10 hover:bg-red-500/40 
            text-white/60 hover:text-white
            opacity-0 group-hover:opacity-100 
            transition-smooth z-50
            cursor-pointer pointer-events-auto
          "
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="text-center animate-fade-in w-full px-6" data-tauri-drag-region>
          <div className="w-24 h-24 mx-auto mb-6 relative" data-tauri-drag-region>
            <div className="absolute inset-0 bg-[#8AB4F8] rounded-[32px] rotate-12 opacity-5 animate-pulse"></div>
            <img 
              src={icon} 
              alt="App Icon" 
              className="w-full h-full object-contain relative z-10"
              data-tauri-drag-region
            />
          </div>
          <h1 className="text-2xl font-bold text-white mb-2 tracking-tight" data-tauri-drag-region>
            Kokoro TTS
          </h1>
          <div 
            key={status}
            className={`
              text-[11px] uppercase tracking-widest font-bold min-h-[1.5rem] animate-text-update
              ${status.includes("Ready") ? "text-emerald-400" : isError ? "text-red-400" : "text-white/40"}
            `}
            data-tauri-drag-region
          >
            {status}{status.includes("Ready") || isError ? "" : dots}
          </div>

          {/* Engine Error log info */}
          {isError && logPath && (
            <div className="mt-4 space-y-2 pointer-events-auto">
              <p className="text-[10px] text-white/40 leading-relaxed">
                A log file was saved. Share it to help diagnose the issue:
              </p>
              <div className="flex items-center gap-1.5 bg-white/5 rounded-lg px-2 py-1.5 border border-white/10">
                <span className="flex-1 text-[9px] text-white/50 font-mono truncate text-left" title={logPath}>
                  {logPath}
                </span>
                <button
                  onClick={handleCopyPath}
                  className="shrink-0 text-[9px] font-bold px-2 py-0.5 rounded bg-white/10 hover:bg-white/20 text-white/60 hover:text-white transition-smooth cursor-pointer"
                >
                  {copied ? "✓" : "Copy"}
                </button>
              </div>
              <button
                onClick={handleOpenFolder}
                className="w-full text-[10px] font-semibold py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/50 hover:text-white/80 transition-smooth cursor-pointer"
              >
                Open Log Folder
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
