import { useEffect, useState, useCallback } from "react";
import { load } from "@tauri-apps/plugin-store";
import { register, unregister, isRegistered } from "@tauri-apps/plugin-global-shortcut";
import { invoke } from "@tauri-apps/api/core";
// ─── Kokoro voice presets ──────────────────────────────────────────────────
const VOICE_PRESETS = [
  "af_alloy",
  "af_aoede",
  "af_bella",
  "af_heart",
  "af_jessica",
  "af_kore",
  "af_nicole",
  "af_nova",
  "af_river",
  "af_sarah",
  "af_sky",
  "am_adam",
  "am_echo",
  "am_eric",
  "am_fenrir",
  "am_liam",
  "am_michael",
  "am_onyx",
  "am_puck",
  "am_santa",
  "bf_alice",
  "bf_emma",
  "bf_isabella",
  "bf_lily",
  "bm_daniel",
  "bm_fable",
  "bm_george",
  "bm_lewis",
] as const;

const DEFAULT_VOICE = "am_fenrir";
const DEFAULT_SHORTCUT_WIN = "Super+Shift+Q";
const DEFAULT_SHORTCUT_MAC = "Command+Shift+Q";

function getPlatformDefault() {
  return navigator.userAgent.includes("Mac")
    ? DEFAULT_SHORTCUT_MAC
    : DEFAULT_SHORTCUT_WIN;
}

export default function SettingsWindow() {
  const [voice, setVoice] = useState(DEFAULT_VOICE);
  const [shortcut, setShortcut] = useState(getPlatformDefault());
  const [shortcutEnabled, setShortcutEnabled] = useState(true);
  const [recording, setRecording] = useState(false);
  const [saved, setSaved] = useState(false);
  
  const [devices, setDevices] = useState<{id: number, name: string}[]>([]);
  const [currentDevice, setCurrentDevice] = useState<number>(0);

  // ── Load settings ──
  useEffect(() => {
    (async () => {
      // 1. Fetch sidecar audio devices
      try {
        const devRes = await invoke<any>("get_audio_devices");
        if (devRes && devRes.devices) {
          setDevices(devRes.devices);
          setCurrentDevice(devRes.current ?? 0);
        }
      } catch (e) {
        console.error("[Kokoro UI] Failed to get audio devices:", e);
      }

      // 2. Fetch local store settings
      const store = await load("settings.json", { defaults: {}, autoSave: true });
      const v = await store.get<string>("voice");
      if (v) setVoice(v);
      const s = await store.get<string>("shortcut");
      if (s) setShortcut(s);
      const e = await store.get<boolean>("shortcut-enabled");
      if (e !== null && e !== undefined) setShortcutEnabled(e);
    })();
  }, []);

  // ── Save settings ──
  const handleSave = useCallback(async () => {
    const store = await load("settings.json", { defaults: {}, autoSave: true });
    await store.set("voice", voice);
    await store.set("shortcut", shortcut);
    await store.set("shortcut-enabled", shortcutEnabled);

    // Re-register the shortcut
    try {
      const platformDefault = getPlatformDefault();
      // Unregister old shortcut if it was registered
      if (await isRegistered(platformDefault)) {
        await unregister(platformDefault);
      }
      if (await isRegistered(shortcut)) {
        await unregister(shortcut);
      }

      if (shortcutEnabled) {
        await register(shortcut, (event) => {
          if (event.state === "Pressed") {
            // The shortcut trigger is handled via event emission
            console.log("[Kokoro] Shortcut triggered");
          }
        });
      }
    } catch (error) {
      console.error("Failed to register shortcut:", error);
    }

    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }, [voice, shortcut, shortcutEnabled]);

  // ── Key recorder ──
  const handleKeyRecord = useCallback((e: React.KeyboardEvent) => {
    if (!recording) return;
    e.preventDefault();

    const parts: string[] = [];
    if (e.metaKey) parts.push("Command");
    if (e.ctrlKey) parts.push("Control");
    if (e.altKey) parts.push("Alt");
    if (e.shiftKey) parts.push("Shift");

    const key = e.key;
    if (!["Control", "Shift", "Alt", "Meta"].includes(key)) {
      parts.push(key.length === 1 ? key.toUpperCase() : key);
      setShortcut(parts.join("+"));
      setRecording(false);
    }
  }, [recording]);

  return (
    <div className="h-full surface-low text-white">
      {/* Title bar */}
      <div
        className="flex items-center justify-between px-5 py-3 border-b border-white/5 bg-white/5"
        data-tauri-drag-region
      >
        <h1 className="text-xs font-bold uppercase tracking-[0.1em] text-white/60">
          Settings
        </h1>
      </div>

      <div className="p-6 space-y-6 animate-fade-in">
        {/* Voice Preset */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-white/50 uppercase tracking-wider">
            Voice Preset
          </label>
          <select
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
            className="
              w-full px-4 py-2.5 rounded-xl
              bg-[#2D2D2D] border border-white/10
              text-sm text-white/90
              focus:outline-none focus:border-[#8AB4F8]/50
              transition-smooth cursor-pointer
            "
          >
            {VOICE_PRESETS.map((v) => (
              <option key={v} value={v} className="bg-[#2D2D2D]">
                {v.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </option>
            ))}
          </select>
        </div>

        {/* Audio Output Device */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-white/50 uppercase tracking-wider">
            Audio Output
          </label>
          <div className="flex gap-2">
            <select
              value={currentDevice}
              onChange={async (e) => {
                const id = parseInt(e.target.value);
                setCurrentDevice(id);
                // Directly tell sidecar to switch device
                await invoke("set_audio_device", { id }).catch(console.error);
              }}
              className="
                flex-1 px-4 py-2.5 rounded-xl
                bg-[#2D2D2D] border border-white/10
                text-sm text-white/90
                focus:outline-none focus:border-[#8AB4F8]/50
                transition-smooth cursor-pointer
              "
            >
              {devices.length === 0 && <option value={0}>Default System Device</option>}
              {devices.map((d) => (
                <option key={d.id} value={d.id} className="bg-[#2D2D2D]">
                  {d.name.substring(0, 40) + (d.name.length > 40 ? "..." : "")}
                </option>
              ))}
            </select>
            <button
              onClick={() => invoke("test_audio")}
              title="Play a test beep"
              className="
                px-5 py-2.5 rounded-xl text-xs font-semibold
                bg-white/5 border border-white/10
                hover:bg-white/10 transition-smooth
                text-white/60 hover:text-[#8AB4F8]
              "
            >
              Test
            </button>
          </div>
        </div>

        {/* Global Shortcut */}
        <div className="space-y-2">
          <label className="text-xs font-medium text-white/50 uppercase tracking-wider">
            Global Shortcut
          </label>
          <div className="flex gap-2">
            <div
              tabIndex={0}
              onClick={() => setRecording(true)}
              onKeyDown={handleKeyRecord}
              onBlur={() => setRecording(false)}
              className={`
                flex-1 px-4 py-2.5 rounded-xl text-sm font-medium
                border transition-smooth cursor-pointer
                ${
                  recording
                    ? "border-[#8AB4F8] bg-[#1C2B41] text-[#D3E3FD]"
                    : "border-white/10 bg-[#2D2D2D] text-white/90"
                }
              `}
            >
              {recording ? "Press keys..." : shortcut}
            </div>
            <button
              onClick={() => {
                setShortcut(getPlatformDefault());
                setRecording(false);
              }}
              className="
                px-4 py-2.5 rounded-xl text-xs font-semibold
                bg-white/5 border border-white/10
                hover:bg-white/10 transition-smooth
                text-white/60 hover:text-white/90
              "
            >
              Reset
            </button>
          </div>
        </div>

        {/* Enable / Disable */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-white/70">Enable Shortcut</span>
          <button
            onClick={() => setShortcutEnabled(!shortcutEnabled)}
            className={`
              w-10 h-5 rounded-full transition-smooth relative
              ${shortcutEnabled ? "bg-[#8AB4F8]" : "bg-white/10"}
            `}
          >
            <span
              className={`
                absolute top-0.5 w-4 h-4 rounded-full shadow-sm
                transition-smooth
                ${shortcutEnabled ? "left-5.5 bg-[#202124]" : "left-0.5 bg-white/40"}
              `}
            />
          </button>
        </div>

        {/* Save */}
        <button
          onClick={handleSave}
          className={`
            w-full py-3.5 rounded-full font-bold text-sm tracking-wide
            transition-smooth shadow-lg
            ${
              saved
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "bg-[#8AB4F8] hover:bg-[#AECBFA] text-[#202124] active:scale-[0.98]"
            }
          `}
        >
          {saved ? "✓ Saved" : "Save Changes"}
        </button>
      </div>
    </div>
  );
}
