import io
import unittest

from scripts.analyze_tts_events import analyze_stream, parse_event_lines


def event_line(event, timestamp, data=None, request_id="request-1"):
    import json

    return "[TTS_EVENT] " + json.dumps(
        {
            "schemaVersion": 1,
            "requestId": request_id,
            "event": event,
            "timestampMs": timestamp,
            "data": data or {},
        }
    )


class AnalyzeTtsEventsTests(unittest.TestCase):
    def test_ignores_unstructured_and_malformed_lines(self):
        lines = [
            "[Sidecar] ordinary log\n",
            "[TTS_EVENT] not-json\n",
            event_line("request_received", 100) + "\n",
        ]

        events = parse_event_lines(lines)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "request_received")

    def test_summarizes_first_audio_and_total_latency(self):
        log = "\n".join(
            [
                event_line(
                    "request_received",
                    100,
                    {"textLength": 42, "voice": "am_fenrir", "speed": 1.0},
                ),
                event_line("engine_ready", 140),
                event_line("inference_started", 150),
                event_line("chunk_ready", 500, {"chunkIndex": 0}),
                event_line("chunk_ready", 700, {"chunkIndex": 1}),
                event_line("playback_started", 620),
                event_line("playback_finished", 2100),
            ]
        )

        summary = analyze_stream(io.StringIO(log))["requests"][0]

        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["metadata"]["textLength"], 42)
        self.assertEqual(summary["durationsMs"]["engineReadyMs"], 40)
        self.assertEqual(summary["durationsMs"]["firstChunkReadyMs"], 400)
        self.assertEqual(summary["durationsMs"]["firstAudioMs"], 520)
        self.assertEqual(summary["durationsMs"]["playbackMs"], 1480)
        self.assertEqual(summary["durationsMs"]["totalMs"], 2000)

    def test_keeps_requests_and_failures_separate(self):
        log = "\n".join(
            [
                event_line("request_received", 100),
                event_line("cancelled", 200),
                event_line("request_received", 300, request_id="request-2"),
                event_line(
                    "error",
                    350,
                    {"stage": "inference", "message": "failed"},
                    request_id="request-2",
                ),
            ]
        )

        requests = analyze_stream(io.StringIO(log))["requests"]

        self.assertEqual([item["status"] for item in requests], ["cancelled", "error"])
        self.assertEqual(requests[1]["errors"][0]["stage"], "inference")


if __name__ == "__main__":
    unittest.main()
