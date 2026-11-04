import math
import random
import unittest

from raster import (Pixel, step_line, dda_line, bresenham_line, bresenham_circle,
                    wu_line, nearest)


LINES = (step_line, dda_line, bresenham_line)


class RasterTests(unittest.TestCase):
    def test_hand_calculated_line_and_decisions(self):
        expected_y = [0, 1, 1, 2, 2, 3, 4, 4, 5, 6, 6, 7, 7, 8]
        expected_d = [3, -7, 9, -1, 15, 5, -5, 11, 1, -9, 7, -3, 13, 3]
        for function in LINES:
            self.assertEqual(function(0, 0, 13, 8), [Pixel(x, y) for x, y in enumerate(expected_y)])
        trace = []
        bresenham_line(0, 0, 13, 8, trace)
        self.assertEqual([step.value for step in trace], expected_d)

    def test_all_octants_and_random_lines(self):
        rng = random.Random(13)
        cases = [(0, 0, x, y) for x in range(-12, 13) for y in range(-12, 13)]
        cases += [tuple(rng.randint(-1000, 1000) for _ in range(4)) for _ in range(100)]
        for function in LINES:
            for x0, y0, x1, y1 in cases:
                points = function(x0, y0, x1, y1)
                self.assertEqual(points[0], Pixel(x0, y0))
                self.assertEqual(points[-1], Pixel(x1, y1))
                self.assertEqual(len(points), max(abs(x1-x0), abs(y1-y0)) + 1)
                self.assertEqual(len(set(points)), len(points))
                for a, b in zip(points, points[1:]):
                    self.assertEqual(max(abs(b.x-a.x), abs(b.y-a.y)), 1)
                denominator = math.hypot(x1-x0, y1-y0)
                if denominator:
                    for p in points:
                        distance = abs((y1-y0)*(p.x-x0)-(x1-x0)*(p.y-y0)) / denominator
                        self.assertLessEqual(distance, 0.500000001)

    def test_degenerate_and_axis_lines(self):
        for function in (*LINES, wu_line):
            self.assertEqual(function(-3, 2, -3, 2), [Pixel(-3, 2)])
            self.assertEqual(function(2, 3, 2, -3), [Pixel(2, y) for y in range(3, -4, -1)])
            self.assertEqual(function(-2, -1, 2, -1), [Pixel(x, -1) for x in range(-2, 3)])

    def test_rounding_at_negative_halves(self):
        self.assertEqual(nearest(-1.5), -1)
        self.assertEqual(nearest(1.5), 2)
        self.assertEqual(dda_line(0, 0, 10, 1)[5], Pixel(5, 1))

    def test_trace_matches_returned_pixels(self):
        for function, args in [(f, (4, -2, -9, 7)) for f in (*LINES, wu_line)] + [
                (bresenham_circle, (-3, 2, 12)), (bresenham_circle, (0, 0, 0))]:
            trace = []
            result = function(*args, trace=trace)
            self.assertEqual(result, [p for step in trace for p in step.pixels])
            self.assertEqual(result, function(*args))

    def test_circle_hand_calculation(self):
        trace = []
        bresenham_circle(0, 0, 8, trace)
        self.assertEqual([(s.x, s.y, s.value) for s in trace],
                         [(0, 8, -13), (1, 8, -7), (2, 8, 3), (3, 7, -11), (4, 7, 7), (5, 6, 5)])

    def test_circle_symmetry_distance_and_connectivity(self):
        for radius in range(1, 81):
            points = bresenham_circle(0, 0, radius)
            coords = {(p.x, p.y) for p in points}
            self.assertEqual(len(coords), len(points))
            for x, y in coords:
                for u, v in ((-x, y), (x, -y), (y, x)):
                    self.assertIn((u, v), coords)
                self.assertLessEqual(abs(math.hypot(x, y)-radius), 0.51)
            for point in [(radius, 0), (-radius, 0), (0, radius), (0, -radius)]:
                self.assertIn(point, coords)
            reached = {next(iter(coords))}
            pending = list(reached)
            while pending:
                x, y = pending.pop()
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        other = x+dx, y+dy
                        if other in coords and other not in reached:
                            reached.add(other)
                            pending.append(other)
            self.assertEqual(reached, coords)

    def test_zero_radius_and_translation(self):
        self.assertEqual(bresenham_circle(-3, 2, 0), [Pixel(-3, 2)])
        self.assertEqual(bresenham_circle(-3, 2, 9),
                         [Pixel(p.x-3, p.y+2) for p in bresenham_circle(0, 0, 9)])

    def test_wu_weights_and_weighted_coordinates(self):
        for x1 in range(-8, 9):
            for y1 in range(-8, 9):
                trace = []
                points = wu_line(2, -3, x1, y1, trace)
                self.assertEqual(len(set((p.x, p.y) for p in points)), len(points))
                for step in trace:
                    self.assertAlmostEqual(sum(p.alpha for p in step.pixels), 1)
                    self.assertAlmostEqual(sum(p.x*p.alpha for p in step.pixels), step.x)
                    self.assertAlmostEqual(sum(p.y*p.alpha for p in step.pixels), step.y)
                    self.assertTrue(all(0 < p.alpha <= 1 for p in step.pixels))

    def test_wu_reversed_segment_has_same_weights(self):
        forward = {(p.x, p.y): p.alpha for p in wu_line(-4, 7, 9, -1)}
        reverse = {(p.x, p.y): p.alpha for p in wu_line(9, -1, -4, 7)}
        self.assertEqual(forward, reverse)

    def test_invalid_values(self):
        for function in (*LINES, wu_line):
            with self.assertRaises(ValueError):
                function(0, 0, 1.5, 2)
        for args in [(0, 0, -1), (0, 0, 1.5), (True, 0, 1)]:
            with self.assertRaises(ValueError):
                bresenham_circle(*args)


if __name__ == '__main__':
    unittest.main()
