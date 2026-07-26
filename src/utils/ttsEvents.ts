export type TtsStatus = "Idle" | "Generating" | "Speaking" | "Paused" | "TTS Error";

export type TtsEventName =
  | "request_received"
  | "engine_ready"
  | "inference_started"
  | "chunk_ready"
  | "playback_started"
  | "paused"
  | "resumed"
  | "speed_changed"
  | "cancelled"
  | "playback_finished"
  | "error";

export type TtsLifecycleEvent = {
  schemaVersion: 1;
  requestId: string;
  event: TtsEventName;
  timestampMs: number;
  data: Record<string, unknown>;
};

export function statusForTtsEvent(event: TtsLifecycleEvent): TtsStatus | null {
  switch (event.event) {
    case "request_received":
      return "Generating";
    case "engine_ready":
    case "inference_started":
    case "chunk_ready":
    case "speed_changed":
      // Informational stages must not move a streaming request back from
      // Speaking to Generating when later chunks arrive.
      return null;
    case "playback_started":
    case "resumed":
      return "Speaking";
    case "paused":
      return "Paused";
    case "cancelled":
    case "playback_finished":
      return "Idle";
    case "error":
      return "TTS Error";
    default:
      return null;
  }
}

export function eventBelongsToRequest(
  event: TtsLifecycleEvent,
  activeRequestId: string | null,
): boolean {
  return activeRequestId !== null && event.requestId === activeRequestId;
}
