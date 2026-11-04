"""Проверка формул на эталонных цветах и независимой библиотеке colorsys."""

import colorsys
import math
import random
import unittest

from colors import (
    ColorState, cmyk_to_rgb, hex_to_rgb, hls_to_rgb,
    rgb_to_cmyk, rgb_to_hex, rgb_to_hls,
)


class ColorTests(unittest.TestCase):
    def assertColorAlmostEqual(self, actual, expected, places=9):
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=places)

    def test_reference_colors(self):
        references = [
            ((0, 0, 0), (0, 0, 0, 100), (0, 0, 0)),
            ((255, 255, 255), (0, 0, 0, 0), (0, 100, 0)),
            ((255, 0, 0), (0, 100, 100, 0), (0, 50, 100)),
            ((255, 255, 0), (0, 0, 100, 0), (60, 50, 100)),
            ((0, 255, 0), (100, 0, 100, 0), (120, 50, 100)),
            ((0, 255, 255), (100, 0, 0, 0), (180, 50, 100)),
            ((0, 0, 255), (100, 100, 0, 0), (240, 50, 100)),
            ((255, 0, 255), (0, 100, 0, 0), (300, 50, 100)),
        ]
        for rgb, cmyk, hls in references:
            with self.subTest(rgb=rgb):
                self.assertColorAlmostEqual(rgb_to_cmyk(*rgb), cmyk)
                self.assertColorAlmostEqual(rgb_to_hls(*rgb), hls)
                self.assertColorAlmostEqual(cmyk_to_rgb(*cmyk), rgb)
                self.assertColorAlmostEqual(hls_to_rgb(*hls), rgb)

    def test_all_gray_levels(self):
        for gray in range(256):
            self.assertColorAlmostEqual(rgb_to_hls(gray, gray, gray), (0, gray / 255 * 100, 0))
            cmyk = rgb_to_cmyk(gray, gray, gray)
            self.assertColorAlmostEqual(cmyk, (0, 0, 0, (1 - gray / 255) * 100))

    def test_hue_wraps_at_360(self):
        self.assertColorAlmostEqual(hls_to_rgb(360, 50, 100), (255, 0, 0))

    def test_achromatic_hls(self):
        for h in (0, 37, 180, 359, 360):
            for s in (0, 32, 100):
                self.assertColorAlmostEqual(hls_to_rgb(h, 0, s), (0, 0, 0))
                self.assertColorAlmostEqual(hls_to_rgb(h, 100, s), (255, 255, 255))
            self.assertColorAlmostEqual(hls_to_rgb(h, 25, 0), (63.75, 63.75, 63.75))

    def test_full_black_ink(self):
        for cmy in ((0, 0, 0), (15, 91, 42), (100, 100, 100)):
            self.assertColorAlmostEqual(cmyk_to_rgb(*cmy, 100), (0, 0, 0))

    def test_rgb_against_standard_library_and_round_trips(self):
        rng = random.Random(13)
        for _ in range(1000):
            rgb = tuple(rng.uniform(0, 255) for _ in range(3))
            h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in rgb))
            expected = h * 360, l * 100, s * 100
            self.assertColorAlmostEqual(rgb_to_hls(*rgb), expected)
            self.assertColorAlmostEqual(hls_to_rgb(*rgb_to_hls(*rgb)), rgb)
            self.assertColorAlmostEqual(cmyk_to_rgb(*rgb_to_cmyk(*rgb)), rgb)

    def test_hls_against_standard_library(self):
        rng = random.Random(42)
        for _ in range(1000):
            h, l, s = rng.random(), rng.random(), rng.random()
            expected = tuple(v * 255 for v in colorsys.hls_to_rgb(h, l, s))
            self.assertColorAlmostEqual(hls_to_rgb(h * 360, l * 100, s * 100), expected)

    def test_arbitrary_cmyk_preserves_color_after_normalization(self):
        rng = random.Random(100)
        for _ in range(1000):
            cmyk = tuple(rng.uniform(0, 100) for _ in range(4))
            rgb = cmyk_to_rgb(*cmyk)
            self.assertColorAlmostEqual(cmyk_to_rgb(*rgb_to_cmyk(*rgb)), rgb)

    def test_hex(self):
        self.assertEqual(hex_to_rgb(" #7c5cfc "), (124, 92, 252))
        self.assertEqual(hex_to_rgb("f80"), (255, 136, 0))
        self.assertEqual(rgb_to_hex((124.1, 91.9, 252)), "#7C5CFC")

    def test_invalid_hex(self):
        for value in ("", "#", "1234", "1234567", "red", "##123456", "#gg0000", "12 345"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                hex_to_rgb(value)

    def test_editing_cmyk_preserves_noncanonical_ink_values(self):
        state = ColorState()
        state.set_values("CMYK", (50, 50, 50, 50))
        self.assertEqual(state.values["CMYK"], (50, 50, 50, 50))
        self.assertColorAlmostEqual(state.values["RGB"], (63.75, 63.75, 63.75))
        state.set_component("CMYK", 0, 75)
        self.assertEqual(state.values["CMYK"], (75, 50, 50, 50))

    def test_hls_hue_survives_when_source_is_black(self):
        state = ColorState()
        state.set_values("HLS", (120, 0, 100))
        self.assertEqual(state.values["HLS"], (120, 0, 100))
        state.set_component("HLS", 1, 50)
        self.assertColorAlmostEqual(state.values["RGB"], (0, 255, 0))

    def test_conversion_does_not_quantize_rgb(self):
        state = ColorState()
        state.set_values("HLS", (17.123, 43.987, 65.432))
        original = state.values["RGB"]
        self.assertNotEqual(original, tuple(round(v) for v in original))
        for _ in range(100):
            state.set_values("CMYK", state.values["CMYK"])
            state.set_values("HLS", state.values["HLS"])
        self.assertColorAlmostEqual(state.values["RGB"], original)

    def test_invalid_values_do_not_change_state(self):
        state = ColorState()
        before = state.values.copy()
        for model, values in (
            ("RGB", (-1, 0, 0)), ("RGB", (256, 0, 0)),
            ("RGB", (math.nan, 0, 0)), ("RGB", (math.inf, 0, 0)),
            ("CMYK", (0, 0, 0, 101)), ("HLS", (361, 50, 100)),
            ("HLS", (120, -0.1, 100)), ("HLS", (120, 50, 100.01)),
            ("RGB", (1, 2)), ("HSV", (0, 0, 0)),
        ):
            with self.subTest(model=model, values=values), self.assertRaises(ValueError):
                state.set_values(model, values)
            self.assertEqual(state.values, before)


if __name__ == "__main__":
    unittest.main()
