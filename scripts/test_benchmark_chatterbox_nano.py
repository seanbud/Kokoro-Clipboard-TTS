import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark_chatterbox_nano import (
    NANO_RUNTIME_FILES,
    directory_size_bytes,
    load_fixtures,
    peak_rss_bytes,
    percentile,
    summarize_runs,
)


class ChatterboxNanoBenchmarkTests(unittest.TestCase):
    def test_percentile_validates_bounds(self):
        self.assertEqual(percentile([40, 10, 30, 20], 50), 20)
        self.assertEqual(percentile([40, 10, 30, 20], 95), 40)
        with self.assertRaises(ValueError):
            percentile([], 95)
        with self.assertRaises(ValueError):
            percentile([1], 101)

    def test_loads_single_latency_and_quality_suites(self):
        with tempfile.TemporaryDirectory() as directory:
            corpus_path = Path(directory) / "corpus.json"
            cases = [
                {"id": fixture_id, "category": "test", "input": fixture_id}
                for fixture_id in [
                    "chat-ok-ellipsis",
                    "technical-identifiers",
                    "structure-paragraph-breaks",
                    "long-form-single-sentence",
                    "extra",
                ]
            ]
            corpus_path.write_text(json.dumps({"cases": cases}), encoding="utf-8")

            self.assertEqual(load_fixtures(corpus_path, "single", "extra")[0]["id"], "extra")
            self.assertEqual(len(load_fixtures(corpus_path, "latency", "extra")), 4)
            self.assertEqual(len(load_fixtures(corpus_path, "quality", "extra")), 5)
            with self.assertRaises(ValueError):
                load_fixtures(corpus_path, "single", "missing")

    def test_summarizes_whole_utterance_latency_and_failures(self):
        summary = summarize_runs([
            {"firstAudioMs": 100, "generationMs": 100, "realTimeFactor": 0.2, "averageCpuCores": 2.0},
            {"firstAudioMs": 300, "generationMs": 300, "realTimeFactor": 0.6, "averageCpuCores": 1.0},
            {"firstAudioMs": 200, "generationMs": 200, "realTimeFactor": 0.4, "averageCpuCores": 1.5},
            {"error": "failed"},
        ])

        self.assertEqual(summary["successfulRuns"], 3)
        self.assertEqual(summary["failedRuns"], 1)
        self.assertEqual(summary["firstAudioMedianMs"], 200)
        self.assertEqual(summary["firstAudioP95Ms"], 300)
        self.assertEqual(summary["realTimeFactorMedian"], 0.4)
        self.assertEqual(summary["averageCpuCoresMedian"], 1.5)

    def test_counts_snapshot_and_loaded_runtime_assets_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime_name = next(iter(NANO_RUNTIME_FILES))
            (root / runtime_name).write_bytes(b"runtime")
            (root / "unused.safetensors").write_bytes(b"unused-large")

            self.assertEqual(directory_size_bytes(root), 19)
            self.assertEqual(directory_size_bytes(root, NANO_RUNTIME_FILES), 7)

    def test_allows_peak_memory_metric_to_be_unavailable_on_windows(self):
        with patch("benchmark_chatterbox_nano.resource", None):
            self.assertIsNone(peak_rss_bytes())


if __name__ == "__main__":
    unittest.main()
