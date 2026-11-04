"""Локальные пороги и повышение резкости. Все изображения — uint8, 0..255."""

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps


def read_image(path):
    """Читаем первый кадр; учитываем EXIF и накладываем прозрачность на белый."""
    with Image.open(Path(path)) as source:
        image = ImageOps.exif_transpose(source)
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        return np.array(Image.alpha_composite(background, rgba).convert("RGB"))


def validate_image(image):
    array = np.asarray(image)
    if array.dtype != np.uint8 or array.size == 0:
        raise ValueError("Нужно непустое изображение uint8")
    if array.ndim != 2 and not (array.ndim == 3 and array.shape[2] == 3):
        raise ValueError("Нужно изображение в оттенках серого или RGB")
    return array


def grayscale(image):
    image = validate_image(image)
    if image.ndim == 2:
        return image.copy()
    brightness = image.astype(np.float64) @ np.array([0.299, 0.587, 0.114])
    return np.rint(brightness).clip(0, 255).astype(np.uint8)


def check_number(value, name, minimum, maximum):
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name}: допустимо от {minimum} до {maximum}")


def local_statistics(gray, window):
    """Среднее и стандартное отклонение через интегральные изображения, O(HW)."""
    gray = validate_image(gray)
    if gray.ndim != 2:
        raise ValueError("Локальная статистика вычисляется для яркости")
    if not isinstance(window, (int, np.integer)) or not 3 <= window <= 151 or window % 2 == 0:
        raise ValueError("Размер окна должен быть нечётным числом от 3 до 151")
    padded = np.pad(gray.astype(np.float64), window // 2, mode="edge")

    def mean_in_window(values):
        integral = np.pad(values, ((1, 0), (1, 0))).cumsum(axis=0).cumsum(axis=1)
        total = (integral[window:, window:] - integral[:-window, window:]
                 - integral[window:, :-window] + integral[:-window, :-window])
        return total / (window * window)

    mean = mean_in_window(padded)
    variance = mean_in_window(padded * padded) - mean * mean
    # Вычитание близких чисел может дать небольшую отрицательную погрешность.
    deviation = np.sqrt(np.maximum(variance, 0))
    return mean, deviation


def local_thresholds(image, window=31, niblack_k=0.2, sauvola_k=0.2):
    """Возвращает бинарные результаты Ниблэка и Сауволы; текст — чёрный."""
    check_number(niblack_k, "k Ниблэка", -1, 1)
    check_number(sauvola_k, "k Сауволы", 0, 1)
    gray = grayscale(image)
    mean, deviation = local_statistics(gray, window)
    niblack_threshold = mean - niblack_k * deviation
    sauvola_threshold = mean * (1 + sauvola_k * (deviation / 128 - 1))
    # Равенство относим к фону. Постоянная область без перепадов остаётся белой.
    niblack = np.where(gray >= niblack_threshold, 255, 0).astype(np.uint8)
    sauvola = np.where(gray >= sauvola_threshold, 255, 0).astype(np.uint8)
    return niblack, sauvola


def laplacian_sharpen(image, amount=0.6):
    """J = I - a*ΔI; ΔI — сумма четырёх соседей минус 4*I."""
    image = validate_image(image)
    check_number(amount, "Коэффициент Лапласа", 0, 3)
    values = image.astype(np.float64)
    padding = ((1, 1), (1, 1)) + (((0, 0),) if image.ndim == 3 else ())
    padded = np.pad(values, padding, mode="edge")
    laplacian = (padded[:-2, 1:-1] + padded[2:, 1:-1]
                 + padded[1:-1, :-2] + padded[1:-1, 2:] - 4 * values)
    return np.rint(values - amount * laplacian).clip(0, 255).astype(np.uint8)


def gaussian_blur(image, sigma):
    """Гауссово ядро разделено на горизонтальную и вертикальную свёртки."""
    image = validate_image(image)
    check_number(sigma, "Сигма", 0.3, 5)
    radius = math.ceil(3 * sigma)
    positions = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(positions * positions) / (2 * sigma * sigma))
    kernel /= kernel.sum()
    values = image.astype(np.float64)
    for axis in (0, 1):
        padding = [(0, 0)] * image.ndim
        padding[axis] = (radius, radius)
        padded = np.pad(values, padding, mode="edge")
        result = np.zeros_like(values)
        for i, weight in enumerate(kernel):
            region = [slice(None)] * image.ndim
            region[axis] = slice(i, i + values.shape[axis])
            result += weight * padded[tuple(region)]
        values = result
    return values


def unsharp_mask(image, amount=1.5, sigma=1.2):
    """J = I + a*(I - Gσ*I). Промежуточные значения не обрезаются."""
    image = validate_image(image)
    check_number(amount, "Коэффициент маски", 0, 5)
    blurred = gaussian_blur(image, sigma)
    values = image.astype(np.float64)
    return np.rint(values + amount * (values - blurred)).clip(0, 255).astype(np.uint8)


def compare(image, mode, parameters):
    if mode == "threshold":
        return local_thresholds(image, **parameters)
    if mode == "sharpen":
        return (laplacian_sharpen(image, parameters["laplacian_amount"]),
                unsharp_mask(image, parameters["unsharp_amount"], parameters["sigma"]))
    raise ValueError(f"Неизвестный режим: {mode}")
