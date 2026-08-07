import unittest

import numpy as np

from sidecar.audio_safety import (
    fade_from_silence,
    fade_to_silence,
    sanitize_audio_buffer,
)


class AudioSafetyTests(unittest.TestCase):
    def test_sanitizes_non_finite_and_out_of_range_samples(self):
        audio = np.array([np.nan, np.inf, -np.inf, 1.8, -2.1, 0.25])

        result = sanitize_audio_buffer(audio)

        self.assertEqual(result.dtype, np.float32)
        self.assertEqual(result.shape, (6, 1))
        np.testing.assert_allclose(
            result[:, 0],
            [0.0, 1.0, -1.0, 1.0, -1.0, 0.25],
        )

    def test_pause_fade_reaches_zero_without_exceeding_last_sample(self):
        result = fade_to_silence(np.array([0.8], dtype=np.float32), sample_count=5)

        self.assertEqual(result.shape, (5, 1))
        self.assertAlmostEqual(float(result[0, 0]), 0.8)
        self.assertAlmostEqual(float(result[-1, 0]), 0.0)
        self.assertTrue(np.all(np.diff(result[:, 0]) <= 0))

    def test_resume_fade_starts_at_zero_and_preserves_the_tail(self):
        audio = np.ones((8, 1), dtype=np.float32)

        result = fade_from_silence(audio, sample_count=4)

        self.assertAlmostEqual(float(result[0, 0]), 0.0)
        self.assertAlmostEqual(float(result[3, 0]), 1.0)
        np.testing.assert_allclose(result[4:, 0], np.ones(4))
        np.testing.assert_allclose(audio[:, 0], np.ones(8))


if __name__ == "__main__":
    unittest.main()
