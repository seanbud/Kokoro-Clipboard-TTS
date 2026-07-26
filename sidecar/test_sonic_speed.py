import unittest

import numpy as np

from sidecar.sonic_speed import SonicSpeedProcessor, native_library_path


@unittest.skipUnless(native_library_path().is_file(), "Sonic DSP must be built first")
class SonicSpeedProcessorTests(unittest.TestCase):
    def test_preserves_pitch_while_changing_duration(self):
        sample_rate = 24_000
        source = np.sin(
            2 * np.pi * 220 * np.arange(sample_rate * 2) / sample_rate
        ).astype(np.float32).reshape(-1, 1)

        # Keep the recommended 0.75x-1.5x listening range covered as well as
        # the advanced range endpoints.
        for speed in (0.5, 0.75, 1.0, 1.5, 2.0):
            with self.subTest(speed=speed):
                with SonicSpeedProcessor(initial_speed=speed) as processor:
                    chunks = [
                        processor.process(source[index:index + 480])
                        for index in range(0, len(source), 480)
                    ]
                    chunks.append(processor.flush())
                output = np.concatenate(chunks, axis=0).reshape(-1)
                expected = len(source) / speed
                self.assertLess(abs(len(output) - expected), sample_rate * 0.03)

                core = output[2000:-2000]
                crossings = np.flatnonzero((core[:-1] <= 0) & (core[1:] > 0))
                estimated_pitch = sample_rate / np.mean(np.diff(crossings))
                self.assertAlmostEqual(estimated_pitch, 220, delta=1)

    def test_speed_change_affects_the_next_twenty_millisecond_buffer(self):
        source = np.zeros((480, 1), dtype=np.float32)
        with SonicSpeedProcessor(initial_speed=1.0) as processor:
            for _ in range(10):
                processor.process(source)
            first_fast_output = processor.process(source, speed=2.0)
            second_fast_output = processor.process(source)

        # Sonic may retain the first changed buffer while finding a pitch period,
        # but produces accelerated output no later than the following 20ms input.
        self.assertLessEqual(len(first_fast_output), 480)
        self.assertGreater(len(second_fast_output), 0)
        self.assertLess(len(second_fast_output), 360)

    def test_rejects_out_of_range_speed(self):
        with SonicSpeedProcessor() as processor:
            with self.assertRaises(ValueError):
                processor.set_speed(0.4)
            with self.assertRaises(ValueError):
                processor.set_speed(2.1)


if __name__ == "__main__":
    unittest.main()
