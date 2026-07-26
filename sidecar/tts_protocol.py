"""Structured lifecycle events shared by the TTS sidecar and its tests.

The sidecar still writes human-readable diagnostics to stdout. Lifecycle events
use a dedicated prefix followed by compact JSON so the Rust process manager can
forward them without inferring application state from log wording.
"""

from __future__ import annotations

import json
import time
from typing import Any


EVENT_PREFIX = "[TTS_EVENT] "
EVENT_SCHEMA_VERSION = 1
DEFAULT_SEGMENT_PAUSE_MS = 200
MAX_SEGMENT_PAUSE_MS = 2_000


def create_tts_event(
    event: str,
    request_id: str,
    *,
    timestamp_ms: int | None = None,
    **data: Any,
) -> dict[str, Any]:
    """Create a validated, JSON-serializable TTS lifecycle event."""

    normalized_event = event.strip()
    normalized_request_id = request_id.strip()
    if not normalized_event:
        raise ValueError("event must not be empty")
    if not normalized_request_id:
        raise ValueError("request_id must not be empty")

    return {
        "schemaVersion": EVENT_SCHEMA_VERSION,
        "requestId": normalized_request_id,
        "event": normalized_event,
        "timestampMs": timestamp_ms if timestamp_ms is not None else time.time_ns() // 1_000_000,
        "data": data,
    }


def encode_tts_event(event: str, request_id: str, **data: Any) -> str:
    """Encode an event as one stdout-safe protocol line."""

    payload = create_tts_event(event, request_id, **data)
    return EVENT_PREFIX + json.dumps(payload, separators=(",", ":"), sort_keys=True)


def normalize_synthesis_segments(
    raw_segments: Any,
    fallback_text: str,
) -> list[dict[str, Any]]:
    """Validate the model-facing subset of a frontend speech plan.

    Empty segments (currently fenced code) remain available to the frontend for
    source mapping but are not sent to the model. Old clients fall back to one
    segment with the v0.6 pause duration.
    """

    normalized = []
    if isinstance(raw_segments, list):
        for index, raw_segment in enumerate(raw_segments):
            if not isinstance(raw_segment, dict):
                continue
            spoken_text = str(
                raw_segment.get("spokenText")
                or raw_segment.get("spoken_text")
                or ""
            ).strip()
            if not spoken_text:
                continue
            raw_pause = raw_segment.get(
                "pauseAfterMs",
                raw_segment.get("pause_after_ms", DEFAULT_SEGMENT_PAUSE_MS),
            )
            try:
                pause_after_ms = int(raw_pause)
            except (TypeError, ValueError):
                pause_after_ms = DEFAULT_SEGMENT_PAUSE_MS
            pause_after_ms = max(0, min(pause_after_ms, MAX_SEGMENT_PAUSE_MS))
            normalized.append(
                {
                    "id": str(raw_segment.get("id") or f"segment-{index}"),
                    "kind": str(raw_segment.get("kind") or "paragraph"),
                    "spoken_text": spoken_text,
                    "pause_after_ms": pause_after_ms,
                }
            )

    if normalized:
        return normalized

    fallback_text = str(fallback_text or "").strip()
    if not fallback_text:
        return []
    return [
        {
            "id": "segment-0",
            "kind": "paragraph",
            "spoken_text": fallback_text,
            "pause_after_ms": DEFAULT_SEGMENT_PAUSE_MS,
        }
    ]
