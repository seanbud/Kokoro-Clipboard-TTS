import json
import unittest

from sidecar.tts_protocol import (
    EVENT_PREFIX,
    EVENT_SCHEMA_VERSION,
    create_tts_event,
    encode_tts_event,
    normalize_synthesis_segments,
)


class TtsProtocolTests(unittest.TestCase):
    def test_creates_versioned_event_with_data(self):
        event = create_tts_event(
            "chunk_ready",
            "request-123",
            timestamp_ms=42,
            chunkIndex=3,
        )

        self.assertEqual(
            event,
            {
                "schemaVersion": EVENT_SCHEMA_VERSION,
                "requestId": "request-123",
                "event": "chunk_ready",
                "timestampMs": 42,
                "data": {"chunkIndex": 3},
            },
        )

    def test_encodes_exactly_one_prefixed_json_line(self):
        line = encode_tts_event("request_received", "request-123", textLength=18)

        self.assertTrue(line.startswith(EVENT_PREFIX))
        self.assertNotIn("\n", line)
        payload = json.loads(line.removeprefix(EVENT_PREFIX))
        self.assertEqual(payload["requestId"], "request-123")
        self.assertEqual(payload["data"]["textLength"], 18)

    def test_rejects_missing_identity_fields(self):
        with self.assertRaises(ValueError):
            create_tts_event("", "request-123")
        with self.assertRaises(ValueError):
            create_tts_event("request_received", "")

    def test_normalizes_model_facing_speech_segments(self):
        segments = normalize_synthesis_segments(
            [
                {
                    "id": "heading-1",
                    "kind": "heading",
                    "spokenText": "  A useful heading  ",
                    "pauseAfterMs": 550,
                    "sourceText": "## A useful heading",
                },
                {"id": "code-1", "kind": "code", "spokenText": ""},
                {"id": "unsafe", "spokenText": "Bounded pause", "pauseAfterMs": 99_999},
            ],
            "unused fallback",
        )

        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["spoken_text"], "A useful heading")
        self.assertEqual(segments[0]["pause_after_ms"], 550)
        self.assertNotIn("sourceText", segments[0])
        self.assertEqual(segments[1]["pause_after_ms"], 2_000)

    def test_falls_back_for_clients_without_a_speech_plan(self):
        segments = normalize_synthesis_segments(None, " Legacy text ")

        self.assertEqual(segments[0]["spoken_text"], "Legacy text")
        self.assertEqual(segments[0]["pause_after_ms"], 200)


if __name__ == "__main__":
    unittest.main()
