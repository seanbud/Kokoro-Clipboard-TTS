import { useEffect, useState } from "react";
import { load } from "@tauri-apps/plugin-store";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";

export default function Tutorial() {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    (async () => {
      const store = await load("settings.json", { defaults: {}, autoSave: true });
      const done = await store.get<boolean>("first-run-done");
      if (done) {
        // Already completed tutorial — hide this window
        const win = getCurrentWebviewWindow();
        await win.hide();
        setVisible(false);
      }
    })();
  }, []);

  const handleDismiss = async () => {
    const store = await load("settings.json", { defaults: {}, autoSave: true });
    await store.set("first-run-done", true);
    setVisible(false);
    const win = getCurrentWebviewWindow();
    await win.hide();
  };

  if (!visible) return null;

  const isMac = navigator.userAgent.includes("Mac");
  const shortcutKey = isMac ? "⌘ + Shift + Q" : "Win + Shift + Q";

  return (
    <div className="h-full flex items-center justify-center bg-gradient-to-br from-gray-950 via-gray-900 to-indigo-950">
      <div className="max-w-sm w-full mx-4 animate-fade-in">
        {/* Icon */}
        <div className="flex justify-center mb-6">
          <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-xl shadow-indigo-500/30">
            <span className="text-4xl">🎙️</span>
          </div>
        </div>

        {/* Title */}
        <h1 className="text-xl font-bold text-white text-center mb-2">
          Welcome to Kokoro TTS
        </h1>
        <p className="text-sm text-white/50 text-center mb-6">
          Your clipboard, read aloud by AI.
        </p>

        {/* Steps */}
        <div className="space-y-4 mb-8">
          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-xs font-bold text-indigo-400">1</span>
            </div>
            <div>
              <p className="text-sm text-white/80 font-medium">Find the tray icon</p>
              <p className="text-xs text-white/40 mt-0.5">
                Kokoro lives in your {isMac ? "menu bar" : "system tray"} at the{" "}
                {isMac ? "top" : "bottom"}-right of your screen.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-xs font-bold text-indigo-400">2</span>
            </div>
            <div>
              <p className="text-sm text-white/80 font-medium">Select text & press the shortcut</p>
              <p className="text-xs text-white/40 mt-0.5">
                Highlight any text, then press{" "}
                <kbd className="px-1.5 py-0.5 rounded bg-white/10 text-white/70 font-mono text-[10px]">
                  {shortcutKey}
                </kbd>{" "}
                to read it aloud.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <div className="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <span className="text-xs font-bold text-indigo-400">3</span>
            </div>
            <div>
              <p className="text-sm text-white/80 font-medium">Control playback</p>
              <p className="text-xs text-white/40 mt-0.5">
                A small reader widget will appear near your cursor. Use it to play, pause, stop, or
                adjust speed.
              </p>
            </div>
          </div>
        </div>

        {/* Dismiss */}
        <button
          onClick={handleDismiss}
          className="
            w-full py-3 rounded-xl font-medium text-sm
            bg-gradient-to-r from-indigo-500 to-purple-600
            hover:from-indigo-400 hover:to-purple-500
            text-white shadow-lg shadow-indigo-500/20
            active:scale-[0.98] transition-smooth
          "
        >
          Got it — Let's go!
        </button>
      </div>
    </div>
  );
}
