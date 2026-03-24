import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { invoke } from "@tauri-apps/api/core";
import { getCurrentWebviewWindow, getAllWebviewWindows } from "@tauri-apps/api/webviewWindow";
import { load } from "@tauri-apps/plugin-store";
import { error } from "@tauri-apps/plugin-log";
import icon from "../assets/icon.png";

export default function Splash() {
  const [status, setStatus] = useState("Initializing...");
  const [dots, setDots] = useState("");

  useEffect(() => {
    const timer = setInterval(() => {
      setDots((d) => (d.length >= 3 ? "" : d + "."));
    }, 500);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    let active = true;
    const unlisten = listen<string>("sidecar-status", (event) => {
      if (!active) return;
      const s = event.payload;
      console.log("[Splash] Status update:", s);
      if (s === "ready") {
        setStatus("Ready");
        setTimeout(() => active && handleReady(), 800);
      } else if (s === "starting") {
        setStatus("Starting TTS Engine");
      } else if (s.startsWith("error")) {
        setStatus("Engine Error");
      }
    });

    // Check initial status
    invoke<string>("get_sidecar_status").then((s) => {
      if (!active) return;
      console.log("[Splash] Initial status:", s);
      if (s === "ready") {
        setStatus("Ready");
        setTimeout(() => active && handleReady(), 800);
      } else if (s === "starting") {
        setStatus("Starting TTS Engine");
      }
    });

    return () => {
      active = false;
      unlisten.then((fn) => fn());
    };
  }, []);

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
            console.log("[Splash] Manual close mouseDown");
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

        <div className="text-center animate-fade-in" data-tauri-drag-region>
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
            key={status} // Triggers animation on status change
            className="text-white/40 text-[11px] uppercase tracking-widest font-bold min-h-[1.5rem] animate-text-update" 
            data-tauri-drag-region
          >
            {status}{status === "Ready" || status.includes("Error") ? "" : dots}
          </div>
        </div>
      </div>
    </div>
  );
}
