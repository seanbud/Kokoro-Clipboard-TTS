import { describe, expect, it } from "vitest";
import {
  eventBelongsToRequest,
  statusForTtsEvent,
  type TtsEventName,
  type TtsLifecycleEvent,
} from "./ttsEvents";

function lifecycleEvent(event: TtsEventName, requestId = "active"): TtsLifecycleEvent {
  return {
    schemaVersion: 1,
    requestId,
    event,
    timestampMs: 42,
    data: {},
  };
}

describe("TTS lifecycle events", () => {
  it("maps lifecycle stages to reader status", () => {
    expect(statusForTtsEvent(lifecycleEvent("request_received"))).toBe("Generating");
    expect(statusForTtsEvent(lifecycleEvent("engine_ready"))).toBeNull();
    expect(statusForTtsEvent(lifecycleEvent("inference_started"))).toBeNull();
    expect(statusForTtsEvent(lifecycleEvent("chunk_ready"))).toBeNull();
    expect(statusForTtsEvent(lifecycleEvent("speed_changed"))).toBeNull();
    expect(statusForTtsEvent(lifecycleEvent("playback_started"))).toBe("Speaking");
    expect(statusForTtsEvent(lifecycleEvent("paused"))).toBe("Paused");
    expect(statusForTtsEvent(lifecycleEvent("resumed"))).toBe("Speaking");
    expect(statusForTtsEvent(lifecycleEvent("cancelled"))).toBe("Idle");
    expect(statusForTtsEvent(lifecycleEvent("playback_finished"))).toBe("Idle");
    expect(statusForTtsEvent(lifecycleEvent("error"))).toBe("TTS Error");
  });

  it("rejects lifecycle events from stale playback sessions", () => {
    expect(eventBelongsToRequest(lifecycleEvent("playback_finished"), "active")).toBe(true);
    expect(eventBelongsToRequest(lifecycleEvent("playback_finished", "stale"), "active")).toBe(false);
    expect(eventBelongsToRequest(lifecycleEvent("playback_finished"), null)).toBe(false);
  });
});
