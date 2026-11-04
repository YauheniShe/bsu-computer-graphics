"""Интеграционные проверки настоящих Tk-виджетов; нужен графический сеанс.

Запуск отдельно: python3 -m unittest discover -s tests -p 'gui_checks.py' -v
"""

import tkinter as tk
import unittest

from app import ColorApp, ERROR, number
from colors import CHANNELS, to_rgb


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.app = ColorApp(cls.root)
        cls.root.update()

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def setUp(self):
        self.app.set_hex("#7C5CFC")
        self.root.update()

    def assertSynchronized(self):
        for model, panel in self.app.panels.items():
            values = self.app.state.values[model]
            for i, value in enumerate(values):
                self.assertAlmostEqual(panel.scales[i].get(), value)
                self.assertAlmostEqual(float(panel.variables[i].get()), value, delta=0.0051)
            for actual, expected in zip(to_rgb(model, values), self.app.state.values["RGB"]):
                self.assertAlmostEqual(actual, expected, places=8)
        self.assertEqual(self.app.hex_var.get(), self.app.state.hex)

    def test_fields_in_every_model_and_channel(self):
        for model, panel in self.app.panels.items():
            for i, channel in enumerate(CHANNELS[model]):
                with self.subTest(model=model, channel=channel[0]):
                    value = channel[2] * 0.4
                    panel.variables[i].set(str(value))
                    self.assertEqual(self.app.state.values[model][i], value)
                    self.assertSynchronized()

    def test_sliders_in_every_model_and_channel(self):
        for model, panel in self.app.panels.items():
            for i, channel in enumerate(CHANNELS[model]):
                with self.subTest(model=model, channel=channel[0]):
                    value = channel[2] * 0.7
                    panel.scales[i].set(value)
                    self.assertAlmostEqual(self.app.state.values[model][i], value)
                    self.assertSynchronized()

    def test_palettes_in_all_models(self):
        for model, panel in self.app.panels.items():
            with self.subTest(model=model):
                before = self.app.state.values[model]
                panel.canvas.event_generate("<Button-1>", x=100, y=50)
                self.root.update()
                actual = self.app.state.values[model]
                x_index, y_index = panel.axes
                self.assertAlmostEqual(actual[x_index], 100 / (panel.WIDTH - 1) * CHANNELS[model][x_index][2])
                self.assertAlmostEqual(actual[y_index], (1 - 50 / (panel.HEIGHT - 1)) * CHANNELS[model][y_index][2])
                for i, old in enumerate(before):
                    if i not in panel.axes:
                        self.assertEqual(actual[i], old)
                self.assertSynchronized()

    def test_axis_selectors_swap_without_changing_color(self):
        panel = self.app.panels["CMYK"]
        before = self.app.state.values.copy()
        panel.axis_vars[0].set("M")
        panel.on_axis_change(0)
        self.assertEqual(panel.axes, (1, 0))
        self.assertEqual(self.app.state.values, before)
        panel.axis_vars[0].set("C")
        panel.on_axis_change(0)

    def test_palette_drag_clamps_edges(self):
        panel = self.app.panels["RGB"]
        panel.canvas.event_generate("<B1-Motion>", x=-20, y=300)
        self.root.update()
        self.assertEqual(self.app.state.values["RGB"][:2], (0, 0))
        self.assertSynchronized()

    def test_invalid_entry_is_harmless_and_restored(self):
        panel = self.app.panels["RGB"]
        before = self.app.state.values.copy()
        for invalid in ("", "-", "256", "nan", "inf", "abc"):
            panel.variables[0].set(invalid)
            self.assertEqual(self.app.state.values, before)
            self.assertEqual(panel.entries[0].cget("highlightcolor"), ERROR)
        panel.finish_entry(0)
        self.assertEqual(panel.variables[0].get(), number(before["RGB"][0]))

    def test_decimal_comma_and_edit_text_preserved(self):
        panel = self.app.panels["HLS"]
        panel.variables[0].set("120,50")
        self.assertEqual(self.app.state.values["HLS"][0], 120.5)
        self.assertEqual(panel.variables[0].get(), "120,50")
        panel.finish_entry(0)
        self.assertSynchronized()

    def test_hex_entry(self):
        self.app.hex_var.set("#F80")
        self.assertTrue(self.app.apply_hex())
        self.assertEqual(self.app.state.hex, "#FF8800")
        self.assertSynchronized()
        before = self.app.state.values.copy()
        self.app.hex_var.set("bad input")
        self.assertFalse(self.app.apply_hex())
        self.assertEqual(self.app.state.values, before)

    def test_help_window(self):
        self.app.show_help()
        self.root.update()
        first = self.app.help_window
        self.app.show_help()
        self.assertIs(first, self.app.help_window)
        self.app.help_window.destroy()

    def test_controls_fit_at_minimum_window_size(self):
        self.root.geometry("1060x850")
        self.root.update()
        for panel in self.app.panels.values():
            for widget in (*panel.entries, *panel.scales, panel.canvas, panel.range_hint):
                with self.subTest(model=panel.model, widget=widget):
                    self.assertTrue(widget.winfo_ismapped())
                    self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight())
                    self.assertGreaterEqual(widget.winfo_rootx(), panel.winfo_rootx())
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), panel.winfo_rootx() + panel.winfo_width())
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), panel.winfo_rooty() + panel.winfo_height())
        status = self.app.status_label
        self.assertTrue(status.winfo_ismapped())
        self.assertGreaterEqual(status.winfo_height(), status.winfo_reqheight())
        self.root.geometry("1140x850")
        self.root.update()


if __name__ == "__main__":
    unittest.main()
