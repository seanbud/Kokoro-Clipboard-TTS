import unittest

from build_sonic_dsp import library_filename


class BuildSonicDspTests(unittest.TestCase):
    def test_uses_platform_specific_library_names(self):
        self.assertEqual(library_filename("Windows"), "sonic_kctts.dll")
        self.assertEqual(library_filename("Darwin"), "libsonic_kctts.dylib")
        self.assertEqual(library_filename("Linux"), "libsonic_kctts.so")


if __name__ == "__main__":
    unittest.main()
