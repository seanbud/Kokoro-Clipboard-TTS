import { useEffect, useState } from "react";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import FloatingWidget from "./components/FloatingWidget";
import SettingsWindow from "./components/SettingsWindow";
import Tutorial from "./components/Tutorial";
import Splash from "./components/Splash";
import "./index.css";

type ViewKind = "reader" | "settings" | "tutorial" | "splash" | "unknown";

function App() {
  const [view, setView] = useState<ViewKind>("unknown");

  useEffect(() => {
    const win = getCurrentWebviewWindow();
    const label = win.label as ViewKind;
    setView(["reader", "settings", "tutorial", "splash"].includes(label) ? label : "reader");
  }, []);

  switch (view) {
    case "reader":
      return <FloatingWidget />;
    case "settings":
      return <SettingsWindow />;
    case "tutorial":
      return <Tutorial />;
    case "splash":
      return <Splash />;
    default:
      return null;
  }
}

export default App;
