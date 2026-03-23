import { useEffect, useState } from "react";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import { listen } from "@tauri-apps/api/event";
import { readText } from "@tauri-apps/plugin-clipboard-manager";
import { invoke } from "@tauri-apps/api/core";
import FloatingWidget from "./components/FloatingWidget";
import SettingsWindow from "./components/SettingsWindow";
import Tutorial from "./components/Tutorial";
import { cleanTextForTTS } from "./utils/textCleaner";
import "./index.css";

type ViewKind = "reader" | "settings" | "tutorial" | "unknown";

function App() {
  const [view, setView] = useState<ViewKind>("unknown");

  useEffect(() => {
    const win = getCurrentWebviewWindow();
    const label = win.label as ViewKind;
    setView(["reader", "settings", "tutorial"].includes(label) ? label : "reader");

    // Listen for global shortcut trigger (only on the reader window)
    if (label === "reader") {
      const unlisten = listen("shortcut-triggered", async () => {
        try {
          const clipboardText = await readText();
          if (clipboardText && clipboardText.trim()) {
            const cleaned = cleanTextForTTS(clipboardText);
            // Show the reader window
            await invoke("move_reader_window", { x: 100, y: 100 });
            // Send to TTS
            await invoke("send_to_tts", { text: cleaned, speed: 1.0, voice: "am_fenrir" });
          }
        } catch (err) {
          console.error("[Kokoro] Shortcut handler error:", err);
        }
      });
      return () => { unlisten.then(fn => fn()); };
    }
  }, []);

  switch (view) {
    case "reader":
      return <FloatingWidget />;
    case "settings":
      return <SettingsWindow />;
    case "tutorial":
      return <Tutorial />;
    default:
      return null;
  }
}

export default App;
