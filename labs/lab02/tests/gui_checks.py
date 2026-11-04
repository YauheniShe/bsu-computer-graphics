"""Нужен графический сеанс: python -m unittest discover -s tests -p gui_checks.py."""

from pathlib import Path
import tempfile
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from app import ImageApp, ROOT, SAMPLES
from processing import compare, local_thresholds, read_image


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.callback_errors = []
        cls.root.report_callback_exception = lambda *error: cls.callback_errors.append(error)
        cls.app = ImageApp(cls.root, auto_load=False)
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def setUp(self):
        defaults = {"window": "31", "niblack_k": "0.2", "sauvola_k": "0.2",
                    "laplacian_amount": "0.6", "unsharp_amount": "1.5", "sigma": "1.2"}
        for key, value in defaults.items():
            self.app.variables[key].set(value)
        self.app.sample_var.set("Текст с тенью и шумом")
        self.app.load_sample()
        self.wait_for_result()

    def wait_for_result(self):
        deadline = time.monotonic() + 5
        while self.app.future is not None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.005)
        self.root.update()
        self.assertIsNone(self.app.future, "Обработка не закончилась за 5 секунд")
        self.assertFalse(self.callback_errors)

    def test_samples_and_both_modes(self):
        for name, (_, mode) in SAMPLES.items():
            with self.subTest(sample=name):
                self.app.sample_var.set(name)
                self.app.load_sample()
                self.wait_for_result()
                self.assertEqual(self.app.mode, mode)
                self.assertIsNotNone(self.app.results)
                for result in self.app.results:
                    self.assertEqual(result.shape[:2], self.app.image.shape[:2])
                    self.assertEqual(result.ndim, 2 if mode == "threshold" else 3)

    def test_save_full_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            for index, expected in enumerate(self.app.results):
                path = Path(directory) / f"result-{index}.png"
                self.assertTrue(self.app.save_result(index, path))
                actual = np.asarray(Image.open(path))
                np.testing.assert_array_equal(actual, expected)
                self.assertEqual(actual.shape, (480, 720))

    def test_parameter_change_invalidates_previous_result(self):
        self.app.variables["window"].set("33")
        self.assertIsNone(self.app.results)
        self.assertEqual(str(self.app.panels[1].save_button.cget("state")), "disabled")
        self.app.process()
        self.wait_for_result()
        self.assertIsNotNone(self.app.results)

    def test_invalid_parameters_and_recovery(self):
        for key, value in (("window", "30"), ("window", ""), ("niblack_k", "nan")):
            self.app.variables[key].set(value)
            self.app.process()
            self.wait_for_result()
            self.assertIsNone(self.app.results)
            self.assertEqual(self.app.status.cget("fg"), "#B4233A")
            self.app.variables[key].set("31" if key == "window" else "0.2")
        self.app.process()
        self.wait_for_result()
        self.assertIsNotNone(self.app.results)

    def test_bad_file_does_not_replace_source(self):
        previous = self.app.image.copy()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-an-image.png"
            path.write_text("not an image")
            self.assertFalse(self.app.load_path(path))
        np.testing.assert_array_equal(self.app.image, previous)

    def test_latest_request_wins(self):
        started, release = threading.Event(), threading.Event()

        def delayed(image, mode, parameters):
            if not started.is_set():
                started.set()
                release.wait(timeout=3)
            return compare(image, mode, parameters)

        with patch("app.compare", side_effect=delayed):
            try:
                self.app.process()
                self.assertTrue(started.wait(timeout=1))
                self.app.sample_var.set("Бледный текст")
                self.app.load_sample()
                release.set()
                self.wait_for_result()
            finally:
                release.set()
        expected = local_thresholds(read_image(ROOT / "samples/faint_text.png"))
        for actual, reference in zip(self.app.results, expected):
            np.testing.assert_array_equal(actual, reference)

    def test_viewer_and_help(self):
        viewer = self.app.panels[1].open_full_size()
        self.root.update()
        self.assertTrue(viewer.winfo_exists())
        viewer.destroy()
        self.app.show_help()
        self.root.update()
        first = self.app.help_window
        self.app.show_help()
        self.assertIs(first, self.app.help_window)
        first.destroy()

    def test_layout_at_minimum_size(self):
        self.root.geometry("1120x720")
        self.root.update()
        for panel in self.app.panels:
            for widget in (panel.title, panel.canvas, panel.view_button, panel.save_button):
                if widget is None:
                    continue
                self.assertTrue(widget.winfo_ismapped())
                if widget is not panel.canvas:
                    self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight())
                self.assertGreaterEqual(widget.winfo_rootx(), panel.winfo_rootx())
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), panel.winfo_rootx() + panel.winfo_width())
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), panel.winfo_rooty() + panel.winfo_height())
        self.assertGreaterEqual(self.app.status.winfo_height(), self.app.status.winfo_reqheight())
        self.root.geometry("1220x780")
        self.root.update()


if __name__ == "__main__":
    unittest.main()
