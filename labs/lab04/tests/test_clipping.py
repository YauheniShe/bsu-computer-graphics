"""Проверки вычислений и форматов входных данных."""

from fractions import Fraction
from pathlib import Path
import random
import unittest

from clipping import (BOTTOM, LEFT, RIGHT, TOP, area2, clip_polygon, cohen_sutherland, outcode,
                      parse_polygons, parse_segments, side_value)


SAMPLES = Path(__file__).resolve().parents[1] / 'samples'
BOX = (-6, -3, 6, 5)
WINDOW = ((-4, -3), (5, -3), (5, 4), (-4, 4))


def interval_result(segment, window):
    a, b = segment
    start, end = Fraction(0), Fraction(1)
    delta = [q - p for p, q in zip(a, b)]
    for p, d, low, high in zip(a, delta, window[:2], window[2:]):
        if d:
            entry, exit_ = sorted((Fraction(low - p, d), Fraction(high - p, d)))
            start, end = max(start, entry), min(end, exit_)
        elif not low <= p <= high:
            return None
    if start > end:
        return None
    return tuple(tuple(p + d * t for p, d in zip(a, delta)) for t in (start, end))


class LineTests(unittest.TestCase):
    def test_codes_and_boundary(self):
        self.assertEqual(outcode((-7, 6), BOX), LEFT | TOP)
        self.assertEqual(outcode((7, -4), BOX), RIGHT | BOTTOM)
        self.assertEqual(outcode((-6, 5), BOX), 0)

    def test_sample_and_trace(self):
        segments, window = parse_segments((SAMPLES / 'segments.txt').read_text())
        trace = []
        self.assertEqual(cohen_sutherland(segments[0], window, trace), ((-6, -2), (6, 4)))
        self.assertEqual([step.codes for step in trace], [(5, 10), (1, 10), (0, 10), (0, 2), (0, 0)])
        self.assertEqual([step.side for step in trace], [BOTTOM, LEFT, TOP, RIGHT, 0])
        self.assertEqual(trace[-1].action, 'Принят')
        self.assertIsNone(cohen_sutherland(segments[1], window))
        self.assertEqual(cohen_sutherland(segments[3], window), ((2, -3), (2, 5)))
        self.assertEqual(cohen_sutherland(segments[4], window), ((-6, -1), (6, -1)))
        self.assertEqual(cohen_sutherland(segments[5], window), ((-6, 4), (-6, 4)))

    def test_inside_outside_and_on_the_edge(self):
        for segment, expected in (
            (((0, 0), (0, 0)), ((0, 0), (0, 0))),
            (((0, 6), (0, 6)), None),
            (((-10, -3), (10, -3)), ((-6, -3), (6, -3))),
            (((-6, -3), (6, 5)), ((-6, -3), (6, 5))),
            (((-8, 5), (0, 9)), None),
            (((-8, 3), (-4, 7)), ((-6, 5), (-6, 5))),
        ):
            with self.subTest(segment=segment):
                self.assertEqual(cohen_sutherland(segment, BOX), expected)
                self.assertEqual(cohen_sutherland(segment[::-1], BOX), expected[::-1] if expected else None)

    def test_random_segments_against_interval_intersection(self):
        randomizer = random.Random(13)
        for _ in range(500):
            xmin, xmax = sorted(randomizer.sample(range(-10, 11), 2))
            ymin, ymax = sorted(randomizer.sample(range(-10, 11), 2))
            window = xmin, ymin, xmax, ymax
            segment = tuple(tuple(Fraction(randomizer.randint(-50, 50), 3) for _ in range(2)) for _ in range(2))
            self.assertEqual(cohen_sutherland(segment, window), interval_result(segment, window))


class PolygonTests(unittest.TestCase):
    def test_sample_and_intermediate_contours(self):
        polygon, window = parse_polygons((SAMPLES / 'polygon.txt').read_text())
        trace = []
        result = clip_polygon(polygon, window, trace)
        expected = {
            (-4, 2), (-4, -3), (5, -3), (5, 1), (2, 4), (-2, 4),
        }
        self.assertEqual(set(result), expected)
        self.assertEqual([len(step.polygon) for step in trace], [5, 5, 6, 6])
        self.assertEqual(area2(result), 113)
        self.assertEqual(set(clip_polygon(polygon[::-1], window[::-1])), expected)

    def test_polygon_inside_empty_and_window_inside(self):
        inside = ((-1, 0), (1, 0), (0, 1))
        outside = ((7, 0), (9, 0), (8, 1))
        container = ((-8, -8), (8, -8), (8, 8), (-8, 8))
        self.assertEqual(clip_polygon(inside, WINDOW), inside)
        self.assertEqual(clip_polygon(outside, WINDOW), ())
        self.assertEqual(set(clip_polygon(container, WINDOW)), set(WINDOW))

    def test_point_and_edge_contact(self):
        polygon, window = parse_polygons((SAMPLES / 'polygon_touch.txt').read_text())
        self.assertEqual(clip_polygon(polygon, window), ((-6, 1),))
        above = ((-2, 4), (0, 4), (2, 4), (2, 6), (-2, 6))
        self.assertEqual(set(clip_polygon(above, WINDOW)), {(-2, 4), (2, 4)})

    def test_slanted_window_and_both_orientations(self):
        polygon, window = parse_polygons((SAMPLES / 'polygon_slanted.txt').read_text())
        result = clip_polygon(polygon, window)
        self.assertGreater(len(result), 3)
        self.assertTrue(any(a.denominator > 1 or b.denominator > 1 for a, b in result))
        for contour in (polygon, window):
            for a, b in zip(contour, contour[1:] + contour[:1]):
                self.assertTrue(all(side_value(a, b, p) >= 0 for p in result))
        self.assertEqual(set(result), set(clip_polygon(polygon, window[::-1])))


class InputTests(unittest.TestCase):
    def test_decimal_inputs_and_empty_line_list(self):
        text = '1\n\n-.5 0 0001 +.125\n-1 -1 1 1\n'
        self.assertEqual(parse_segments(text), ((((Fraction(-1, 2), 0), (1, Fraction(1, 8))),), (-1, -1, 1, 1)))
        self.assertEqual(parse_segments('0\n-1 -1 1 1\n'), ((), (-1, -1, 1, 1)))

    def test_incorrect_segment_files(self):
        for text in ('', '2\n0 0 1 1\n-1 -1 1 1', '1\n0 0 nan 0\n-1 -1 1 1',
                     '1\n0 0 1001 0\n-1 -1 1 1', '0\n2 -1 2 1', '0\n2 -1 1 1', '0\n-1 -1 1 1 2'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_segments(text)

    def test_concave_crossing_duplicate_and_collinear_vertices(self):
        window = '4\n-4 -3\n5 -3\n5 4\n-4 4\n'
        for polygon in ('5\n0 0\n4 0\n2 1\n4 4\n0 4\n', '4\n0 0\n4 5\n4 0\n0 4\n',
                        '4\n0 0\n4 0\n4 0\n0 4\n', '3\n0 0\n1 1\n2 2\n'):
            with self.subTest(polygon=polygon), self.assertRaises(ValueError):
                parse_polygons(polygon + window)
        polygon, _ = parse_polygons('5\n0 0\n2 0\n4 0\n0 4\n0 0\n' + window)
        self.assertEqual(polygon, ((0, 0), (2, 0), (4, 0), (0, 4)))


if __name__ == '__main__':
    unittest.main()
