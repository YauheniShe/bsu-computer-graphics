"""Проверки настоящих Tk-виджетов; нужен графический сеанс."""

import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import app as application
from app import RasterApp, LINE, CIRCLE, WU


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.errors = []
        cls.root.report_callback_exception = lambda *error: cls.errors.append(error)
        cls.app = RasterApp(cls.root)
        cls.root.update()
        time.sleep(0.2)
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def setUp(self):
        self.app.stop_play()
        self.app.algorithm.set(LINE)
        self.app.preset.set('Отрезок (0, 0) → (13, 8)')
        self.app.load_preset()
        self.root.update()

    def tearDown(self):
        self.root.update()
        self.assertEqual(self.errors, [])

    def test_initial_pixels_grid_axes_and_labels(self):
        self.assertEqual(len(self.app.pixels), 14)
        self.assertEqual(len(self.app.canvas.find_withtag('pixel')), 14)
        self.assertEqual(len(self.app.table.get_children()), 14)
        self.assertEqual(len(self.app.canvas.find_withtag('axis')), 2)
        self.assertGreater(len(self.app.canvas.find_withtag('grid')), 10)
        self.assertGreater(len(self.app.canvas.find_withtag('coordinate')), 10)

    def test_table_selects_real_algorithm_step(self):
        self.app.table.selection_set('4')
        self.root.update()
        self.assertEqual(self.app.count, 5)
        self.assertEqual(len(self.app.canvas.find_withtag('pixel')), 5)
        self.assertEqual(self.app.trace[4].pixels[0][:2], (4, 2))
        self.assertIn('(4, 2)', self.app.step_details.cget('text'))

    def test_circle_and_wu_modes(self):
        self.app.preset.set('Смещённая окружность')
        self.app.load_preset()
        self.root.update()
        self.assertEqual(self.app.active_name, CIRCLE)
        self.assertTrue(self.app.circle_fields.winfo_ismapped())
        self.assertFalse(self.app.line_fields.winfo_ismapped())
        self.assertEqual(self.app.geometry, (-3, 2, 6))
        self.assertEqual(self.app.canvas.type(self.app.canvas.find_withtag('ideal')[0]), 'oval')
        self.app.preset.set('Сглаженный отрезок')
        self.app.load_preset()
        self.root.update()
        self.assertEqual(self.app.active_name, WU)
        self.assertTrue(any(0 < p.alpha < 1 for p in self.app.pixels))

    def test_invalid_input_preserves_last_result_and_recovers(self):
        before = self.app.pixels[:]
        for value in ('abc', 'nan', '1.5', '1001'):
            self.app.fields['x1'].set(value)
            self.assertFalse(self.app.rebuild())
            self.assertEqual(self.app.pixels, before)
            self.assertIn('Не построено', self.app.status.get())
        self.app.fields['x1'].set('-5')
        self.assertTrue(self.app.rebuild())
        self.assertEqual(self.app.pixels[-1][:2], (-5, 8))

    def test_pixel_centers_round_trip_zoom_anchor_and_pan(self):
        for x, y in [(0, 0), (-4, 8), (13, -5)]:
            actual = self.app.world(*self.app.screen(x, y))
            self.assertAlmostEqual(actual[0], x)
            self.assertAlmostEqual(actual[1], y)
        anchor = self.app.world(151, 233)
        self.app.zoom_at(self.app.scale*1.2, 151, 233)
        self.assertAlmostEqual(self.app.world(151, 233)[0], anchor[0])
        self.assertAlmostEqual(self.app.world(151, 233)[1], anchor[1])
        previous = self.app.ox, self.app.oy
        self.app.drag = (100, 100, *previous)
        self.app.pan(SimpleNamespace(x=120, y=85))
        self.assertAlmostEqual(self.app.ox, previous[0]+20)
        self.assertAlmostEqual(self.app.oy, previous[1]-15)

    def test_fit_includes_large_geometry_and_origin(self):
        for key, value in zip(('x0', 'y0', 'x1', 'y1'), (-1000, -1000, 1000, 1000)):
            self.app.fields[key].set(str(value))
        self.app.rebuild(fit=True)
        for point in [(-1000, -1000), (1000, 1000), (0, 0)]:
            x, y = self.app.screen(*point)
            self.assertGreater(x, 0)
            self.assertGreater(y, 0)
            self.assertLess(x, self.app.canvas.winfo_width())
            self.assertLess(y, self.app.canvas.winfo_height())

    def test_animation_advances_and_stops(self):
        self.app.toggle_play()
        self.assertEqual(self.app.count, 1)
        until = time.monotonic()+0.3
        while time.monotonic() < until:
            self.root.update()
            time.sleep(0.01)
        self.assertGreater(self.app.count, 1)
        self.app.stop_play()
        self.assertIsNone(self.app.play_id)

    def test_benchmark_background_and_save(self):
        data = {'cpu': 'test', 'python': '3', 'repeats': 5,
                'rows': [{'algorithm': LINE, 'size': 13, 'median_us': 12.345}]}
        with patch.object(application, 'measure', return_value=data):
            self.app.start_benchmark()
            deadline = time.monotonic()+3
            while self.app.future is not None and time.monotonic() < deadline:
                self.root.update()
                time.sleep(0.01)
        self.assertIsNone(self.app.future)
        self.assertEqual(self.app.bench_data, data)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'times.json'
            with patch.object(application.filedialog, 'asksaveasfilename', return_value=str(path)):
                self.app.save_benchmark()
            self.assertEqual(json.loads(path.read_text()), data)
        self.app._load_saved_benchmark()

    def test_minimum_window_has_visible_controls(self):
        self.root.geometry('1120x780')
        self.root.update()
        for preset in ('Отрезок (0, 0) → (13, 8)', 'Окружность, R = 8'):
            self.app.preset.set(preset)
            self.app.load_preset()
            self.root.update()
            for tab in (0, 1):
                self.app.tabs.select(tab)
                self.root.update()
                for widget in (self.app.canvas, self.app.play_button, self.app.description,
                               self.app.table if tab == 0 else self.app.bench_button):
                    self.assertTrue(widget.winfo_ismapped())
                    self.assertGreater(widget.winfo_width(), 20)
                    self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight() if widget is not self.app.table and widget is not self.app.canvas else 150)
                    self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(), self.root.winfo_rootx()+self.root.winfo_width())
                    self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(), self.root.winfo_rooty()+self.root.winfo_height())
        self.app.tabs.select(0)
        self.root.geometry('1280x850')


if __name__ == '__main__':
    unittest.main()
