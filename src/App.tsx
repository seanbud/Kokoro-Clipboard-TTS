import { useEffect, useState } from "react";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import FloatingWidget from "./components/FloatingWidget";
import SettingsWindow from "./components/SettingsWindow";
import Tutorial from "./components/Tutorial";
import "./index.css";

type ViewKind = "reader" | "settings" | "tutorial" | "unknown";

function App() {
  const [view, setView] = useState<ViewKind>("unknown");

  useEffect(() => {
    const win = getCurrentWebviewWindow();
    const label = win.label as ViewKind;
    setView(["reader", "settings", "tutorial"].includes(label) ? label : "reader");
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
