"""Растровые алгоритмы. Целочисленная координата обозначает центр пикселя."""

from dataclasses import dataclass
from math import floor
from typing import NamedTuple


class Pixel(NamedTuple):
    x: int
    y: int
    alpha: float = 1.0


@dataclass(frozen=True)
class Step:
    x: float
    y: float
    value: float | None
    pixels: tuple[Pixel, ...]
    action: str


def nearest(value):
    """Ближайшее целое, половины вверх; допуск убирает ошибку накопления ЦДА."""
    return floor(value + 0.5 + 1e-10)


def check_integers(*values):
    if any(type(value) is not int for value in values):
        raise ValueError("Координаты и радиус должны быть целыми числами")


def step_line(x0, y0, x1, y1, trace=None):
    """Пошаговый метод: вычисляем вторую координату из уравнения прямой."""
    check_integers(x0, y0, x1, y1)
    dx, dy = x1 - x0, y1 - y0
    length = max(abs(dx), abs(dy))
    if length == 0:
        return _point(x0, y0, trace)
    major_x = abs(dx) >= abs(dy)
    sign = 1 if (dx if major_x else dy) > 0 else -1
    slope = dy / dx if major_x else dx / dy
    result = []
    for i in range(length + 1):
        if major_x:
            x = x0 + sign * i
            y = y0 + slope * (x - x0)
        else:
            y = y0 + sign * i
            x = x0 + slope * (y - y0)
        pixel = Pixel(nearest(x), nearest(y))
        result.append(pixel)
        if trace is not None:
            trace.append(Step(x, y, None, (pixel,), "по уравнению"))
    return result


def dda_line(x0, y0, x1, y1, trace=None):
    """ЦДА: прибавляем dx/L и dy/L к вещественным координатам."""
    check_integers(x0, y0, x1, y1)
    dx, dy = x1 - x0, y1 - y0
    length = max(abs(dx), abs(dy))
    if length == 0:
        return _point(x0, y0, trace)
    step_x, step_y = dx / length, dy / length
    x, y = float(x0), float(y0)
    result = []
    for i in range(length + 1):
        pixel = Pixel(nearest(x), nearest(y))
        result.append(pixel)
        if trace is not None:
            trace.append(Step(x, y, None, (pixel,), "прибавить dx/L, dy/L"))
        x += step_x
        y += step_y
    return result


def bresenham_line(x0, y0, x1, y1, trace=None):
    """Брезенхем для всех октантов. d>=0 означает диагональный шаг."""
    check_integers(x0, y0, x1, y1)
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    major_x = dx >= dy
    major, minor = (dx, dy) if major_x else (dy, dx)
    error = 2 * minor - major
    x, y = x0, y0
    result = []
    for i in range(major + 1):
        pixel = Pixel(x, y)
        result.append(pixel)
        diagonal = error >= 0
        if trace is not None:
            action = "конец" if i == major else ("диагональ" if diagonal else "прямо")
            trace.append(Step(x, y, error, (pixel,), action))
        if diagonal:
            if major_x:
                y += sy
            else:
                x += sx
            error -= 2 * major
        if major_x:
            x += sx
        else:
            y += sy
        error += 2 * minor
    return result


def bresenham_circle(cx, cy, radius, trace=None):
    """Один октант и восемь симметрий. d0=3-2r, без sqrt и тригонометрии."""
    check_integers(cx, cy, radius)
    if radius < 0:
        raise ValueError("Радиус не может быть отрицательным")
    x, y, error = 0, radius, 3 - 2 * radius
    result, seen = [], set()
    while x <= y:
        points = []
        for u, v in ((x, y), (-x, y), (x, -y), (-x, -y),
                     (y, x), (-y, x), (y, -x), (-y, -x)):
            position = cx + u, cy + v
            if position not in seen:
                seen.add(position)
                points.append(Pixel(*position))
        result.extend(points)
        diagonal = error >= 0
        if trace is not None:
            trace.append(Step(x, y, error, tuple(points), "x+1, y-1" if diagonal else "x+1"))
        if diagonal:
            error += 4 * (x - y) + 10
            y -= 1
        else:
            error += 4 * x + 6
        x += 1
    return result


def wu_line(x0, y0, x1, y1, trace=None):
    """Двухпиксельная схема Ву для целых концов, концы закрашиваются полностью."""
    check_integers(x0, y0, x1, y1)
    dx, dy = x1 - x0, y1 - y0
    length = max(abs(dx), abs(dy))
    if length == 0:
        return _point(x0, y0, trace)
    major_x = abs(dx) >= abs(dy)
    sign = 1 if (dx if major_x else dy) > 0 else -1
    minor_start = y0 if major_x else x0
    minor_delta = dy if major_x else dx
    result = []
    for i in range(length + 1):
        major = (x0 if major_x else y0) + sign * i
        # Целые остатки точно задают веса, в том числе у отрицательных координат.
        low, remainder = divmod(minor_start * length + minor_delta * i, length)
        fraction = remainder / length
        points = []
        for minor, alpha in ((low, 1 - fraction), (low + 1, fraction)):
            if alpha > 0:
                points.append(Pixel(major, minor, alpha) if major_x else Pixel(minor, major, alpha))
        result.extend(points)
        if trace is not None:
            x, y = (major, low + fraction) if major_x else (low + fraction, major)
            trace.append(Step(x, y, fraction, tuple(points), "веса 1-f и f"))
    return result


def _point(x, y, trace):
    pixel = Pixel(x, y)
    if trace is not None:
        trace.append(Step(x, y, None, (pixel,), "точка"))
    return [pixel]


ALGORITHMS = {
    "Пошаговый": step_line,
    "ЦДА": dda_line,
    "Брезенхем — отрезок": bresenham_line,
    "Брезенхем — окружность": bresenham_circle,
    "Ву — сглаживание": wu_line,
}
