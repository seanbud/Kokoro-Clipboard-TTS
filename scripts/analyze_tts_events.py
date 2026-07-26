#!/usr/bin/env python3
"""Convert sidecar lifecycle logs into request-level benchmark JSON.

Usage:
    python scripts/analyze_tts_events.py path/to/kokoro-sidecar.log --pretty
    cat kokoro-sidecar.log | python scripts/analyze_tts_events.py -

The output contains request IDs, non-sensitive request metadata, event timing,
and derived durations. Clipboard text is never part of the lifecycle protocol.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable, TextIO


EVENT_PREFIX = "[TTS_EVENT] "


def parse_event_lines(lines: Iterable[str]) -> list[dict[str, Any]]:
    events = []
    for line in lines:
        marker = line.find(EVENT_PREFIX)
        if marker < 0:
            continue
        payload = line[marker + len(EVENT_PREFIX):].strip()
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if (
            event.get("schemaVersion") == 1
            and isinstance(event.get("requestId"), str)
            and isinstance(event.get("event"), str)
            and isinstance(event.get("timestampMs"), int)
            and isinstance(event.get("data", {}), dict)
        ):
            events.append(event)
    return events


def _duration(timestamps: dict[str, int], end: str, start: str) -> int | None:
    if end not in timestamps or start not in timestamps:
        return None
    return timestamps[end] - timestamps[start]


def summarize_events(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for event in events:
        grouped.setdefault(event["requestId"], []).append(event)

    requests = []
    for request_id, request_events in grouped.items():
        request_events.sort(key=lambda item: item["timestampMs"])
        timestamps: dict[str, int] = {}
        metadata: dict[str, Any] = {}
        errors = []
        status = "incomplete"

        for event in request_events:
            name = event["event"]
            timestamps.setdefault(name, event["timestampMs"])
            if name == "request_received":
                metadata = {
                    key: event["data"][key]
                    for key in ("textLength", "voice", "speed")
                    if key in event["data"]
                }
            elif name == "error":
                errors.append(
                    {
                        key: event["data"][key]
                        for key in ("stage", "message")
                        if key in event["data"]
                    }
                )
                status = "error"
            elif name == "cancelled" and status != "error":
                status = "cancelled"
            elif name == "playback_finished" and status not in {"error", "cancelled"}:
                status = "completed"

        durations = {
            "engineReadyMs": _duration(timestamps, "engine_ready", "request_received"),
            "inferenceStartMs": _duration(timestamps, "inference_started", "request_received"),
            "firstChunkReadyMs": _duration(timestamps, "chunk_ready", "request_received"),
            "firstAudioMs": _duration(timestamps, "playback_started", "request_received"),
            "playbackMs": _duration(timestamps, "playback_finished", "playback_started"),
            "totalMs": _duration(timestamps, "playback_finished", "request_received"),
        }

        requests.append(
            {
                "requestId": request_id,
                "status": status,
                "metadata": metadata,
                "timestampsMs": timestamps,
                "durationsMs": durations,
                "errors": errors,
                "eventCount": len(request_events),
            }
        )

    return {"schemaVersion": 1, "requests": requests}


def analyze_stream(stream: TextIO) -> dict[str, Any]:
    return summarize_events(parse_event_lines(stream))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", default="-", help="Sidecar log path or - for stdin")
    parser.add_argument("--output", "-o", help="Write JSON to this path instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    if args.input == "-":
        result = analyze_stream(sys.stdin)
    else:
        with Path(args.input).open(encoding="utf-8") as stream:
            result = analyze_stream(stream)

    rendered = json.dumps(result, indent=2 if args.pretty else None, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
