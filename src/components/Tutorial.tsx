import { useEffect, useState } from "react";
import { load } from "@tauri-apps/plugin-store";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";

export default function Tutorial() {
  const [visible, setVisible] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        console.log("[Kokoro] Initializing Tutorial...");
        const store = await load("settings.json", { defaults: {}, autoSave: true });
        const done = await store.get<boolean>("first-run-done");
        console.log("[Kokoro] first-run-done status:", done);
        
        if (done) {
          const win = getCurrentWebviewWindow();
          await win.hide();
          setVisible(false);
        }
      } catch (err) {
        console.error("[Kokoro] Tutorial init failed:", err);
        setError(String(err));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleDismiss = async () => {
    try {
      const store = await load("settings.json", { defaults: {}, autoSave: true });
      await store.set("first-run-done", true);
      setVisible(false);
      const win = getCurrentWebviewWindow();
      await win.hide();
    } catch (err) {
      console.error("[Kokoro] Dismiss failed:", err);
    }
  };

  if (loading) return (
    <div className="h-full flex items-center justify-center bg-[#1A1A1A] text-white/20 text-xs">
      Loading...
    </div>
  );
  
  if (error) return (
    <div className="h-full flex items-center justify-center bg-[#1A1A1A] p-8">
      <div className="text-red-400 text-xs font-mono bg-red-400/10 p-4 rounded-xl border border-red-400/20">
        Error: {error}
      </div>
    </div>
  );

  if (!visible) return null;

  const isMac = navigator.userAgent.includes("Mac");
  const shortcutKey = isMac ? "⌘ + Shift + Q" : "Win + Shift + Q";

  console.log("[Kokoro] Rendering Tutorial UI...");

  return (
    <div className="h-full flex items-center justify-center bg-[#1A1A1A]">
      <div className="max-w-sm w-full mx-4 animate-fade-in bg-[#2D2D2D] border border-white/10 p-8 rounded-[32px]">
        {/* Icon */}
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-3xl bg-[#1C2B41] flex items-center justify-center shadow-lg">
            <span className="text-3xl">🎙️</span>
          </div>
        </div>

        {/* Title */}
        <h1 className="text-lg font-bold text-white text-center mb-1">
          Welcome to Kokoro TTS
        </h1>
        <p className="text-xs text-white/40 text-center mb-8">
          The fast, 100% local clipboard reader.
        </p>

        {/* Steps */}
        <div className="space-y-5 mb-10">
          <div className="flex items-start gap-4">
            <div className="w-6 h-6 rounded-full bg-[#8AB4F8]/10 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-[10px] font-bold text-[#8AB4F8]">1</span>
            </div>
            <div>
              <p className="text-[13px] text-white/80 font-semibold tracking-tight">Find the tray icon</p>
              <p className="text-[11px] text-white/30 mt-0.5 leading-relaxed">
                Kokoro lives in your {isMac ? "menu bar" : "system tray"} at the{" "}
                {isMac ? "top" : "bottom"}-right.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="w-6 h-6 rounded-full bg-[#8AB4F8]/10 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-[10px] font-bold text-[#8AB4F8]">2</span>
            </div>
            <div>
              <p className="text-[13px] text-white/80 font-semibold tracking-tight">Select & press shortcut</p>
              <p className="text-[11px] text-white/30 mt-0.5 leading-relaxed">
                Highlight text, then press{" "}
                <kbd className="px-1.5 py-0.5 rounded-md bg-white/5 text-white/50 font-mono text-[9px] border border-white/5">
                  {shortcutKey}
                </kbd>
              </p>
            </div>
          </div>

          <div className="flex items-start gap-4">
            <div className="w-6 h-6 rounded-full bg-[#8AB4F8]/10 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-[10px] font-bold text-[#8AB4F8]">3</span>
            </div>
            <div>
              <p className="text-[13px] text-white/80 font-semibold tracking-tight">Control playback</p>
              <p className="text-[11px] text-white/30 mt-0.5 leading-relaxed">
                A small pill widget will appear near your cursor. Use it to play/stop or change speed.
              </p>
            </div>
          </div>
        </div>

        {/* Dismiss */}
        <button
          onClick={handleDismiss}
          className="
            w-full py-3.5 rounded-full font-bold text-sm
            bg-[#8AB4F8] hover:bg-[#AECBFA]
            text-[#202124] shadow-md
            active:scale-[0.98] transition-smooth
          "
        >
          Sounds good
        </button>
      </div>
    </div>
  );
}
