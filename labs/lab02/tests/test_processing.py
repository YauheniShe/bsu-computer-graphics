import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from processing import (
    compare, gaussian_blur, grayscale, laplacian_sharpen,
    local_statistics, local_thresholds, read_image, unsharp_mask,
)


class ProcessingTests(unittest.TestCase):
    def test_grayscale_primary_colors(self):
        image = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]]], dtype=np.uint8)
        np.testing.assert_array_equal(grayscale(image), [[76, 150, 29]])

    def test_local_statistics_against_direct_windows(self):
        rng = np.random.default_rng(13)
        for shape in ((1, 1), (2, 3), (7, 9)):
            image = rng.integers(0, 256, shape, dtype=np.uint8)
            for window in (3, 5, 31):
                with self.subTest(shape=shape, window=window):
                    padded = np.pad(image, window // 2, mode="edge").astype(float)
                    mean, std = local_statistics(image, window)
                    for y, x in np.ndindex(shape):
                        region = padded[y:y + window, x:x + window]
                        self.assertAlmostEqual(mean[y, x], region.mean(), places=10)
                        self.assertAlmostEqual(std[y, x], region.std(), places=9)

    def test_thresholds_against_direct_formula(self):
        image = np.array([[40, 80, 130], [50, 95, 180], [110, 150, 240]], dtype=np.uint8)
        padded = np.pad(image, 1, mode="edge")
        expected_n, expected_s = np.zeros_like(image), np.zeros_like(image)
        for y, x in np.ndindex(image.shape):
            region = padded[y:y + 3, x:x + 3].astype(float)
            mean, std = region.mean(), region.std()
            expected_n[y, x] = 255 if image[y, x] >= mean - 0.3 * std else 0
            expected_s[y, x] = 255 if image[y, x] >= mean * (1 + 0.4 * (std / 128 - 1)) else 0
        actual_n, actual_s = local_thresholds(image, 3, 0.3, 0.4)
        np.testing.assert_array_equal(actual_n, expected_n)
        np.testing.assert_array_equal(actual_s, expected_s)

    def test_flat_regions_are_background_including_ties(self):
        for value in (0, 127, 255):
            for output in local_thresholds(np.full((4, 5), value, dtype=np.uint8), window=5):
                np.testing.assert_array_equal(output, np.full((4, 5), 255, dtype=np.uint8))

    def test_laplacian_step(self):
        image = np.array([[100, 100, 150, 150]], dtype=np.uint8)
        np.testing.assert_array_equal(laplacian_sharpen(image, 1), [[100, 50, 200, 150]])

    def test_laplacian_clips_instead_of_uint8_overflow(self):
        image = np.array([[10, 10, 250, 250]], dtype=np.uint8)
        np.testing.assert_array_equal(laplacian_sharpen(image, 1), [[10, 0, 255, 250]])

    def test_separable_gaussian_against_direct_2d_convolution(self):
        image = np.array([[10, 20, 30], [90, 100, 250]], dtype=np.uint8)
        sigma = 0.7
        radius = math.ceil(3 * sigma)
        kernel = np.array([[math.exp(-(x * x + y * y) / (2 * sigma * sigma))
                            for x in range(-radius, radius + 1)]
                           for y in range(-radius, radius + 1)])
        kernel /= kernel.sum()
        padded = np.pad(image, radius, mode="edge").astype(float)
        expected = np.zeros_like(image, dtype=float)
        for y, x in np.ndindex(image.shape):
            expected[y, x] = np.sum(padded[y:y + len(kernel), x:x + len(kernel)] * kernel)
        np.testing.assert_allclose(gaussian_blur(image, sigma), expected, atol=1e-10)
        expected_sharp = np.rint(image.astype(float) + 1.3 * (image - expected)).clip(0, 255).astype(np.uint8)
        np.testing.assert_array_equal(unsharp_mask(image, 1.3, sigma), expected_sharp)

    def test_sharpening_preserves_constants_and_zero_amount(self):
        rng = np.random.default_rng(21)
        for shape in ((1, 1), (5, 6), (5, 6, 3)):
            image = rng.integers(0, 256, shape, dtype=np.uint8)
            np.testing.assert_array_equal(laplacian_sharpen(image, 0), image)
            np.testing.assert_array_equal(unsharp_mask(image, 0), image)
            constant = np.full(shape, 137, dtype=np.uint8)
            np.testing.assert_array_equal(laplacian_sharpen(constant, 2), constant)
            np.testing.assert_array_equal(unsharp_mask(constant, 4, 3), constant)

    def test_rgb_channels_do_not_mix(self):
        rng = np.random.default_rng(8)
        image = rng.integers(0, 256, (5, 6, 3), dtype=np.uint8)
        for method in (laplacian_sharpen, unsharp_mask):
            output = method(image)
            for channel in range(3):
                np.testing.assert_array_equal(output[:, :, channel], method(image[:, :, channel]))

    def test_input_is_not_modified(self):
        image = np.arange(60, dtype=np.uint8).reshape(4, 5, 3)
        original = image.copy()
        local_thresholds(image, window=3)
        laplacian_sharpen(image)
        unsharp_mask(image)
        np.testing.assert_array_equal(image, original)

    def test_invalid_parameters(self):
        image = np.zeros((3, 4), dtype=np.uint8)
        for window in (0, 2, 152, 3.5):
            with self.subTest(window=window), self.assertRaises(ValueError):
                local_thresholds(image, window=window)
        calls = [lambda: local_thresholds(image, niblack_k=2),
                 lambda: local_thresholds(image, sauvola_k=-1),
                 lambda: local_thresholds(image, sauvola_k=math.nan),
                 lambda: laplacian_sharpen(image, -1),
                 lambda: unsharp_mask(image, math.inf),
                 lambda: unsharp_mask(image, sigma=0),
                 lambda: compare(image, "other", {})]
        for call in calls:
            with self.assertRaises(ValueError):
                call()

    def test_invalid_images(self):
        for image in (np.zeros((0, 2), dtype=np.uint8), np.zeros((2, 2)),
                      np.zeros((2, 2, 4), dtype=np.uint8), np.zeros(3, dtype=np.uint8)):
            with self.assertRaises(ValueError):
                grayscale(image)

    def test_loading_transparency_and_exif(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "alpha.png"
            image = Image.new("RGBA", (2, 1))
            image.putdata([(0, 0, 0, 0), (10, 20, 30, 255)])
            image.save(path)
            np.testing.assert_array_equal(read_image(path), [[[255, 255, 255], [10, 20, 30]]])
            path = Path(directory) / "rotated.jpg"
            image = Image.new("RGB", (2, 3), "red")
            exif = image.getexif()
            exif[274] = 6
            image.save(path, exif=exif)
            self.assertEqual(read_image(path).shape, (2, 3, 3))

    def test_sample_set_shows_both_threshold_methods_winning(self):
        samples = Path(__file__).resolve().parents[1] / "samples"
        truth = np.asarray(Image.open(samples / "text_mask.png")) == 0
        scores = {}
        for name in ("shadow_text.png", "faint_text.png"):
            outputs = local_thresholds(read_image(samples / name))
            scores[name] = [np.count_nonzero((output == 0) & truth) /
                            np.count_nonzero((output == 0) | truth) for output in outputs]
        self.assertGreater(scores["shadow_text.png"][1], 0.85)
        self.assertGreater(scores["shadow_text.png"][1], scores["shadow_text.png"][0])
        self.assertGreater(scores["faint_text.png"][0], 0.8)
        self.assertGreater(scores["faint_text.png"][0], scores["faint_text.png"][1])

    def test_sample_set_shows_sharpening_and_noise_amplification(self):
        samples = Path(__file__).resolve().parents[1] / "samples"
        reference = read_image(samples / "sharp_reference.png").astype(float)
        for name, improves in (("blurred_shapes.png", True), ("noisy_shapes.png", False)):
            image = read_image(samples / name)
            original_mse = np.mean((image.astype(float) - reference) ** 2)
            for output in (laplacian_sharpen(image), unsharp_mask(image)):
                mse = np.mean((output.astype(float) - reference) ** 2)
                if improves:
                    self.assertLess(mse, original_mse)
                else:
                    self.assertGreater(mse, original_mse)


if __name__ == "__main__":
    unittest.main()
