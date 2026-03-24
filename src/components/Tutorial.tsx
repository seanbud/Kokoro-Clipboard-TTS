
import { load } from "@tauri-apps/plugin-store";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import { error } from "@tauri-apps/plugin-log";

export default function Tutorial() {


  const handleDismiss = async () => {
    try {
      const store = await load("settings.json", { defaults: {}, autoSave: false });
      await store.set("first-run-done", true);
      await store.save();
      const win = getCurrentWebviewWindow();
      await win.hide();
    } catch (err) {
      error(`[Kokoro UI] Dismiss failed: ${err}`);
    }
  };

  const isMac = navigator.userAgent.includes("Mac");
  const shortcutKey = isMac ? "⌘ + Shift + Q" : "Win + Shift + Q";

  return (
    <div className="window-wrapper" data-tauri-drag-region>
      <div 
        className="content-container w-[520px] h-[580px] flex items-center justify-center cursor-default bg-[#1A1A1A] !overflow-visible" 
        data-tauri-drag-region 
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Overlapping Icon */}
        <div className="absolute -top-10 left-1/2 -translate-x-1/2 z-50" data-tauri-drag-region>
          <div className="w-24 h-24 rounded-[32px] bg-[#1C2B41] flex items-center justify-center shadow-2xl relative" data-tauri-drag-region>
            <span className="text-7xl select-none" data-tauri-drag-region>🎙️</span>
          </div>
        </div>

        <div className="w-full px-12 py-12 mt-8" data-tauri-drag-region>
          {/* Title */}
          <h1 className="text-3xl font-bold text-white text-center mb-2 tracking-tight" data-tauri-drag-region>
            Welcome to Kokoro TTS
          </h1>
          <p className="text-base text-white/40 text-center mb-12" data-tauri-drag-region>
            The fast, 100% local clipboard reader.
          </p>

          {/* Steps */}
          <div className="space-y-8 mb-12" data-tauri-drag-region>
            <div className="flex items-start gap-6">
              <div className="w-10 h-10 rounded-full bg-[#8AB4F8]/10 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
                <span className="text-sm font-bold text-[#8AB4F8]">1</span>
              </div>
              <div>
                <p className="text-[19px] text-white/90 font-semibold tracking-tight">Find the tray icon</p>
                <p className="text-[15px] text-white/30 mt-1 leading-relaxed">
                  Kokoro lives in your {isMac ? "menu bar" : "system tray"} at the{" "}
                  {isMac ? "top" : "bottom"}-right.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-6">
              <div className="w-10 h-10 rounded-full bg-[#8AB4F8]/10 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
                <span className="text-sm font-bold text-[#8AB4F8]">2</span>
              </div>
              <div>
                <p className="text-[19px] text-white/90 font-semibold tracking-tight">Copy & press shortcut</p>
                <p className="text-[15px] text-white/30 mt-1 leading-relaxed">
                  Copy text to clipboard, then press{" "}
                  <kbd className="px-2.5 py-0.5 rounded-lg bg-white/5 text-white/50 font-mono text-xs border border-white/5 ml-1">
                    {shortcutKey}
                  </kbd>
                </p>
              </div>
            </div>

            <div className="flex items-start gap-6">
              <div className="w-10 h-10 rounded-full bg-[#8AB4F8]/10 flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm">
                <span className="text-sm font-bold text-[#8AB4F8]">3</span>
              </div>
              <div>
                <p className="text-[19px] text-white/90 font-semibold tracking-tight">Control playback</p>
                <p className="text-[15px] text-white/30 mt-1 leading-relaxed">
                  A small pill widget will appear near your cursor. Use it to play/stop or change speed.
                </p>
              </div>
            </div>
          </div>

          {/* Dismiss */}
          <button
            onClick={handleDismiss}
            className="
              w-full py-5 rounded-full font-bold text-lg
              bg-[#8AB4F8] hover:bg-[#AECBFA]
              text-[#202124] shadow-xl
              active:scale-[0.98] transition-smooth
            "
          >
            Sounds good!
          </button>
        </div>
      </div>
    </div>
  );
}
