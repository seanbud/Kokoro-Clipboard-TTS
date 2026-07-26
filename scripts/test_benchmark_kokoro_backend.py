import json
import tempfile
import unittest
from pathlib import Path

from scripts.benchmark_kokoro_backend import (
    load_fixture,
    percentile,
    summarize_by_fixture,
    summarize_runs,
)


class BenchmarkKokoroBackendTests(unittest.TestCase):
    def test_nearest_rank_percentile(self):
        self.assertEqual(percentile([40, 10, 30, 20], 50), 20)
        self.assertEqual(percentile([40, 10, 30, 20], 95), 40)
        with self.assertRaises(ValueError):
            percentile([], 95)

    def test_summarizes_runs(self):
        summary = summarize_runs(
            [
                {"firstChunkMs": 100.0, "realTimeFactor": 0.5},
                {"firstChunkMs": 300.0, "realTimeFactor": 0.7},
                {"firstChunkMs": 200.0, "realTimeFactor": 0.6},
            ]
        )

        self.assertEqual(summary["firstChunkMedianMs"], 200.0)
        self.assertEqual(summary["firstChunkP95Ms"], 300.0)
        self.assertEqual(summary["realTimeFactorMedian"], 0.6)
        self.assertEqual(summary["successfulRuns"], 3)
        self.assertEqual(summary["failedRuns"], 0)

    def test_loads_fixture_by_id_without_copying_corpus_logic(self):
        with tempfile.TemporaryDirectory() as directory:
            corpus_path = Path(directory) / "corpus.json"
            corpus_path.write_text(
                json.dumps(
                    {
                        "cases": [
                            {"id": "first", "input": "One", "category": "test"},
                            {"id": "second", "input": "Two", "category": "test"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            fixture = load_fixture(corpus_path, "second")

            self.assertEqual(fixture["input"], "Two")
            with self.assertRaises(ValueError):
                load_fixture(corpus_path, "missing")

    def test_summarizes_each_fixture_independently(self):
        summary = summarize_by_fixture(
            [
                {"fixtureId": "a", "firstChunkMs": 100.0, "realTimeFactor": 0.5},
                {"fixtureId": "b", "firstChunkMs": 300.0, "realTimeFactor": 0.7},
                {"fixtureId": "a", "firstChunkMs": 200.0, "realTimeFactor": 0.6},
            ]
        )

        self.assertEqual(summary["a"]["firstChunkMedianMs"], 150.0)
        self.assertEqual(summary["b"]["firstChunkMedianMs"], 300.0)

    def test_reports_failed_runs_without_hiding_successful_metrics(self):
        summary = summarize_runs(
            [
                {"firstChunkMs": 100.0, "realTimeFactor": 0.5},
                {"errorType": "RuntimeError", "error": "unsupported"},
            ]
        )

        self.assertEqual(summary["successfulRuns"], 1)
        self.assertEqual(summary["failedRuns"], 1)
        self.assertEqual(summary["firstChunkMedianMs"], 100.0)


if __name__ == "__main__":
    unittest.main()
