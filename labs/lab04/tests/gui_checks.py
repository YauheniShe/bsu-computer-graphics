"""Проверки настоящих Tk-виджетов; нужен графический сеанс."""

from pathlib import Path
from tempfile import TemporaryDirectory
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app import ClippingApp, LINES, POLYGON


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.errors = []
        cls.root.report_callback_exception = lambda *error: cls.errors.append(error)
        cls.app = ClippingApp(cls.root)
        cls.root.update()
        cls.app.fit()

    @classmethod
    def tearDownClass(cls):
        cls.app.close()

    def setUp(self):
        self.app.algorithm.set(LINES)
        self.app.preset.set('Пересечения с окном')
        self.app.load_preset()
        self.app.source_visible.set(True)
        self.app.redraw()
        self.root.update()

    def tearDown(self):
        self.root.update()
        self.assertEqual(self.errors, [])

    def test_initial_scene_and_source_toggle(self):
        canvas = self.app.canvas
        self.assertEqual(len(canvas.find_withtag('axis')), 2)
        self.assertGreater(len(canvas.find_withtag('grid')), 10)
        self.assertEqual(len(canvas.find_withtag('source')), 6)
        self.assertEqual(len(canvas.find_withtag('visible')), 5)
        self.assertEqual(canvas.type(canvas.find_withtag('visible')[-1]), 'oval')
        self.assertEqual(len(canvas.find_withtag('window')), 1)
        self.app.source_visible.set(False)
        self.app.redraw()
        self.assertFalse(canvas.find_withtag('source'))
        self.assertEqual(len(canvas.find_withtag('visible')), 5)

    def test_table_selection_and_playback(self):
        self.app.table.selection_set('1')
        self.root.update()
        self.assertEqual(self.app.step_index, 1)
        self.assertIn('(-6, -2)', self.app.details.cget('text'))
        self.assertTrue(self.app.canvas.find_withtag('step'))
        self.app.show_all()
        self.app.toggle_play()
        self.assertEqual(self.app.step_index, 0)
        deadline = time.monotonic() + 2
        while self.app.step_index == 0 and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertEqual(self.app.step_index, 1)
        self.app.show_all()
        self.assertIsNone(self.app.play_id)
        self.assertIsNone(self.app.step_index)

    def test_select_segment_and_polygon_modes(self):
        self.app.objects.current(1)
        self.app.objects.event_generate('<<ComboboxSelected>>')
        self.root.update()
        self.assertEqual(self.app.table.item('0', 'values')[-1], 'Отклонён')
        self.app.algorithm.set(POLYGON)
        self.app.change_algorithm()
        self.assertEqual(self.app.active_name, POLYGON)
        self.assertEqual(len(self.app.result[0]), 6)
        self.assertTrue(self.app.canvas.find_withtag('visible-fill'))
        self.app.show_step(1)
        self.assertTrue(self.app.canvas.find_withtag('edge'))
        self.app.preset.set('Касание в точке')
        self.app.load_preset()
        self.assertEqual(self.app.canvas.type(self.app.canvas.find_withtag('visible')[0]), 'oval')

    def test_invalid_input_preserves_result_and_mode_drafts(self):
        previous = self.app.result
        self.app.set_input('4\n1')
        self.assertFalse(self.app.rebuild())
        self.assertEqual(self.app.result, previous)
        self.assertIn('Не отсечено', self.app.status.get())
        for mode in (POLYGON, LINES, POLYGON, LINES):
            self.app.algorithm.set(mode)
            self.app.change_algorithm()
        self.assertEqual(self.app.active_name, LINES)
        self.assertEqual(self.app.result, previous)
        self.assertEqual(self.app.input.get('1.0', 'end-1c'), '4\n1')
        self.app.load_preset()
        self.assertEqual(self.app.result, previous)

    def test_open_file_with_bom_and_failed_open(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'данные.txt'
            path.write_text('1\n-3 0 3 0\n-1 -1 1 1\n', encoding='utf-8-sig')
            with patch('app.filedialog.askopenfilename', return_value=str(path)):
                self.app.open_file()
                self.assertEqual(self.app.result, [((-1, 0), (1, 0))])
                before = self.app.input.get('1.0', 'end-1c')
                path.write_text('неполные данные', encoding='utf-8')
                self.app.open_file()
                self.assertEqual(self.app.input.get('1.0', 'end-1c'), before)
                path.write_bytes(b'\xff\xfe')
                self.app.open_file()
                self.assertIn('Не удалось открыть файл', self.app.status.get())

    def test_fit_zoom_pan_and_minimum_window(self):
        self.root.geometry('1120x780')
        self.root.update()
        self.assertTrue(self.app.rebuild('1\n-1000 -1000 1000 1000\n-1 -1 1 1', fit=True))
        for point in ((0, 0), (-1000, -1000), (1000, 1000)):
            x, y = self.app.screen(*point)
            self.assertTrue(0 < x < self.app.canvas.winfo_width())
            self.assertTrue(0 < y < self.app.canvas.winfo_height())
        anchor = self.app.world(151, 233)
        self.app.zoom_at(self.app.scale * 1.2, 151, 233)
        for a, b in zip(anchor, self.app.world(151, 233)):
            self.assertAlmostEqual(a, b)
        ox, oy = self.app.ox, self.app.oy
        self.app.drag = (100, 100, ox, oy)
        self.app.pan(SimpleNamespace(x=120, y=85))
        self.assertEqual((self.app.ox, self.app.oy), (ox + 20, oy - 15))
        self.assertGreater(self.app.table.winfo_height(), 40)
        self.root.geometry('1280x850')
        self.root.update()


if __name__ == '__main__':
    unittest.main()
