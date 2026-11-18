"""Отсечение отрезков и выпуклых многоугольников."""

from fractions import Fraction
import re
from typing import NamedTuple


LEFT, RIGHT, BOTTOM, TOP = 1, 2, 4, 8
SIDES = {LEFT: 'слева', RIGHT: 'справа', BOTTOM: 'снизу', TOP: 'сверху'}
COORDINATE = re.compile(r'[+-]?(?:[0-9]{1,4}(?:\.[0-9]{0,6})?|\.[0-9]{1,6})')


class LineStep(NamedTuple):
    codes: tuple[int, int]
    side: int
    segment: tuple | None
    action: str


class PolygonStep(NamedTuple):
    edge: tuple
    polygon: tuple


def read_coordinates(tokens, count, label):
    if len(tokens) != count:
        raise ValueError(f'{label}: нужно координат — {count}.')
    if any(not COORDINATE.fullmatch(token) for token in tokens):
        raise ValueError(f'{label}: введите числа с точкой и не более чем шестью знаками после неё.')
    values = tuple(Fraction(token) for token in tokens)
    if any(abs(value) > 1000 for value in values):
        raise ValueError(f'{label}: координаты должны быть от −1000 до 1000.')
    return values


def read_count(line, minimum, label):
    if len(line) != 1 or not re.fullmatch(r'[0-9]{1,3}', line[0]):
        raise ValueError(f'{label}: введите число от {minimum} до 200.')
    count = int(line[0])
    if not minimum <= count <= 200:
        raise ValueError(f'{label}: введите число от {minimum} до 200.')
    return count


def rows(text):
    return [line.split() for line in text.splitlines() if line.strip()]


def parse_segments(text):
    lines = rows(text)
    if not lines:
        raise ValueError('Введите число отрезков, их координаты и прямоугольное окно.')
    count = read_count(lines[0], 0, 'Число отрезков')
    if len(lines) != count + 2:
        raise ValueError(f'После числа отрезков нужно строк с координатами: {count} для отрезков и 1 для окна.')
    segments = []
    for i, line in enumerate(lines[1:-1], 1):
        x0, y0, x1, y1 = read_coordinates(line, 4, f'Отрезок {i}')
        segments.append(((x0, y0), (x1, y1)))
    xmin, ymin, xmax, ymax = read_coordinates(lines[-1], 4, 'Прямоугольное окно')
    if xmin >= xmax or ymin >= ymax:
        raise ValueError('Для окна требуется xmin < xmax и ymin < ymax.')
    return tuple(segments), (xmin, ymin, xmax, ymax)


def edges(points):
    return zip(points[-1:] + points[:-1], points)


def area2(points):
    return sum(a[0] * b[1] - a[1] * b[0] for a, b in edges(points))


def side_value(a, b, p):
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def check_polygon(points, label):
    if points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 3 or len(set(points)) != len(points):
        raise ValueError(f'{label}: нужно не менее трёх различных вершин без повторов.')
    area = area2(points)
    if area == 0:
        raise ValueError(f'{label}: площадь должна быть положительной.')
    orientation = 1 if area > 0 else -1
    if any(orientation * side_value(a, b, p) < 0 for a, b in edges(points) for p in points):
        raise ValueError(f'{label}: перечислите вершины выпуклого многоугольника по порядку обхода.')
    return points


def parse_polygons(text):
    lines = rows(text)
    polygons = []
    for label in ('Исходный многоугольник', 'Окно'):
        if not lines:
            raise ValueError(f'{label}: введите число вершин и их координаты.')
        count = read_count(lines[0], 3, f'{label}, число вершин')
        if len(lines) <= count:
            raise ValueError(f'{label}: нужно строк с вершинами — {count}.')
        points = tuple(read_coordinates(line, 2, f'{label}, вершина {i}')
                       for i, line in enumerate(lines[1:count+1], 1))
        polygons.append(check_polygon(points, label))
        lines = lines[count+1:]
    if lines:
        raise ValueError('После вершин окна есть лишние строки.')
    return tuple(polygons)


def outcode(point, window):
    x, y = point
    xmin, ymin, xmax, ymax = window
    code = 0
    if x < xmin:
        code |= LEFT
    elif x > xmax:
        code |= RIGHT
    if y < ymin:
        code |= BOTTOM
    elif y > ymax:
        code |= TOP
    return code


def cohen_sutherland(segment, window, trace=None):
    """Отсекаем внешние концы по явному уравнению прямой."""
    a, b = segment
    x0, y0 = a
    dx, dy = b[0] - x0, b[1] - y0
    xmin, ymin, xmax, ymax = window
    slope = Fraction(dy, dx) if dx else None
    while True:
        ca, cb = outcode(a, window), outcode(b, window)
        if (ca | cb) == 0:
            result = (a, b)
            if trace is not None:
                trace.append(LineStep((ca, cb), 0, result, 'Принят'))
            return result
        if ca & cb:
            if trace is not None:
                trace.append(LineStep((ca, cb), 0, None, 'Отклонён'))
            return None
        code = ca or cb
        if code & (TOP | BOTTOM):
            side = TOP if code & TOP else BOTTOM
            y = ymax if side == TOP else ymin
            x = x0 if slope is None else x0 + (y - y0) / slope
        else:
            side = RIGHT if code & RIGHT else LEFT
            x = xmax if side == RIGHT else xmin
            y = y0 + slope * (x - x0)
        if ca:
            a = (x, y)
        else:
            b = (x, y)
        if trace is not None:
            trace.append(LineStep((ca, cb), side, (a, b), 'Пересечение'))


def clip_polygon(polygon, window, trace=None):
    """Сазерленд — Ходжман: последовательно оставляем внутренние полуплоскости."""
    orientation = 1 if area2(window) > 0 else -1
    for a, b in zip(window, window[1:] + window[:1]):
        if not polygon:
            break
        result = []
        previous = polygon[-1]
        d0 = orientation * side_value(a, b, previous)
        for point in polygon:
            d1 = orientation * side_value(a, b, point)
            if (d0 >= 0) != (d1 >= 0):
                t = Fraction(d0, d0 - d1)
                intersection = tuple(p + t * (q - p) for p, q in zip(previous, point))
                if not result or result[-1] != intersection:
                    result.append(intersection)
            if d1 >= 0 and (not result or result[-1] != point):
                result.append(point)
            previous, d0 = point, d1
        if len(result) > 1 and result[0] == result[-1]:
            result.pop()
        if len(result) > 2 and area2(result) == 0:
            result = [min(result), max(result)]
        polygon = tuple(result)
        if trace is not None:
            trace.append(PolygonStep((a, b), polygon))
    return polygon
