import sys
import unittest
from unittest.mock import patch

from benchmark_pocket_tts import peak_rss_bytes, summarize_runs


class PocketTtsBenchmarkTests(unittest.TestCase):
    def test_summarizes_success_and_failure_without_model_dependency(self):
        summary = summarize_runs([
            {"firstChunkMs": 100, "realTimeFactor": 0.2},
            {"firstChunkMs": 200, "realTimeFactor": 0.4},
            {"firstChunkMs": 300, "realTimeFactor": 0.6},
            {"error": "failed"},
        ])

        self.assertEqual(summary["successfulRuns"], 3)
        self.assertEqual(summary["failedRuns"], 1)
        self.assertEqual(summary["firstChunkMedianMs"], 200)
        self.assertEqual(summary["firstChunkP95Ms"], 300)
        self.assertEqual(summary["realTimeFactorMedian"], 0.4)

    def test_reports_empty_success_summary(self):
        summary = summarize_runs([{"error": "failed"}])
        self.assertEqual(summary["successfulRuns"], 0)
        self.assertIsNone(summary["firstChunkMedianMs"])

    def test_normalizes_unix_peak_memory_to_bytes(self):
        fake_resource = unittest.mock.Mock()
        fake_resource.RUSAGE_SELF = 0
        fake_resource.getrusage.return_value.ru_maxrss = 123
        with (
            patch("benchmark_pocket_tts.resource", fake_resource),
            patch.object(sys, "platform", "linux"),
        ):
            self.assertEqual(peak_rss_bytes(), 123 * 1024)

    def test_allows_memory_metric_to_be_unavailable_on_windows(self):
        with patch("benchmark_pocket_tts.resource", None):
            self.assertIsNone(peak_rss_bytes())


if __name__ == "__main__":
    unittest.main()
