"""Преобразования RGB ↔ CMYK и RGB ↔ HLS без сторонних библиотек.

Диапазоны: RGB — 0..255, CMYK — 0..100 %, H — 0..360°, L/S — 0..100 %.
Промежуточные вычисления выполняются с float, без округления.
"""

import math


CHANNELS = {
    "RGB": (("R", "Красный", 255), ("G", "Зелёный", 255), ("B", "Синий", 255)),
    "CMYK": (
        ("C", "Голубой", 100), ("M", "Пурпурный", 100),
        ("Y", "Жёлтый", 100), ("K", "Чёрный", 100),
    ),
    "HLS": (("H", "Цветовой тон", 360), ("L", "Светлота", 100), ("S", "Насыщенность", 100)),
}


def rgb_to_cmyk(r, g, b):
    """Упрощённая модель CMYK с максимальным выделением чёрного."""
    r, g, b = r / 255, g / 255, b / 255
    maximum = max(r, g, b)
    if maximum == 0:  # У чёрного K=100%; делить на 1-K нельзя.
        return 0.0, 0.0, 0.0, 100.0
    return (
        (1 - r / maximum) * 100,
        (1 - g / maximum) * 100,
        (1 - b / maximum) * 100,
        (1 - maximum) * 100,
    )


def cmyk_to_rgb(c, m, y, k):
    black_factor = 1 - k / 100
    return tuple(255 * (1 - ink / 100) * black_factor for ink in (c, m, y))


def rgb_to_hls(r, g, b):
    r, g, b = r / 255, g / 255, b / 255
    maximum, minimum = max(r, g, b), min(r, g, b)
    delta = maximum - minimum
    lightness = (maximum + minimum) / 2
    if delta == 0:  # У серого тон не определён; выбираем H=0, S=0.
        return 0.0, lightness * 100, 0.0

    saturation = delta / (1 - abs(2 * lightness - 1))
    if maximum == r:
        hue = ((g - b) / delta) % 6
    elif maximum == g:
        hue = (b - r) / delta + 2
    else:
        hue = (r - g) / delta + 4
    return hue * 60, lightness * 100, min(saturation, 1.0) * 100


def hls_to_rgb(h, l, s):
    # H=360° и H=0° обозначают один и тот же тон.
    sector, lightness, saturation = (h % 360) / 60, l / 100, s / 100
    chroma = (1 - abs(2 * lightness - 1)) * saturation
    x = chroma * (1 - abs(sector % 2 - 1))
    offset = lightness - chroma / 2
    if sector < 1:
        components = chroma, x, 0
    elif sector < 2:
        components = x, chroma, 0
    elif sector < 3:
        components = 0, chroma, x
    elif sector < 4:
        components = 0, x, chroma
    elif sector < 5:
        components = x, 0, chroma
    else:
        components = chroma, 0, x
    return tuple(max(0.0, min(255.0, (v + offset) * 255)) for v in components)


def rgb_to_hex(rgb):
    """Округление до 8 бит используется только для экрана и HEX."""
    return "#" + "".join(f"{max(0, min(255, round(v))):02X}" for v in rgb)


def hex_to_rgb(text):
    value = text.strip().removeprefix("#")
    if len(value) == 3:
        value = "".join(char * 2 for char in value)
    if len(value) != 6 or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise ValueError("Введите HEX: #7C5CFC или #F80")
    return tuple(float(int(value[i:i + 2], 16)) for i in (0, 2, 4))


def to_rgb(model, values):
    if model == "RGB":
        return tuple(values)
    if model == "CMYK":
        return cmyk_to_rgb(*values)
    if model == "HLS":
        return hls_to_rgb(*values)
    raise ValueError(f"Неизвестная модель: {model}")


class ColorState:
    """Один цвет, представленный в трёх моделях.

    Введённые координаты исходной модели сохраняются. Это важно для
    неоднозначного CMYK и для тона HLS при нулевой насыщенности.
    Две другие модели вычисляются через RGB с полной точностью.
    """

    def __init__(self, color="#7C5CFC"):
        self.values = {}
        self.set_values("RGB", hex_to_rgb(color))

    def set_values(self, model, values):
        if model not in CHANNELS or len(values) != len(CHANNELS[model]):
            raise ValueError("Неверная модель или число компонентов")
        values = tuple(float(value) for value in values)
        for value, (symbol, _, maximum) in zip(values, CHANNELS[model]):
            if not math.isfinite(value) or not 0 <= value <= maximum:
                raise ValueError(f"{model} · {symbol}: допустимы значения от 0 до {maximum}")

        rgb = to_rgb(model, values)
        self.values = {"RGB": rgb, "CMYK": rgb_to_cmyk(*rgb), "HLS": rgb_to_hls(*rgb)}
        self.values[model] = values

    def set_component(self, model, index, value):
        values = list(self.values[model])
        values[index] = value
        self.set_values(model, values)

    @property
    def hex(self):
        return rgb_to_hex(self.values["RGB"])
