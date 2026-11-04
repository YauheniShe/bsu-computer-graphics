"""Пересчитать измерения: python compare_samples.py."""

from pathlib import Path

import numpy as np
from PIL import Image

from processing import laplacian_sharpen, local_thresholds, read_image, unsharp_mask


def build_report():
    samples = Path(__file__).resolve().parent / "samples"
    truth = np.asarray(Image.open(samples / "text_mask.png")) == 0
    lines = ["# Сравнение на примерах", "", "Получено командой `python compare_samples.py`.", "",
             "## Локальные пороги", "", "Окно 31 × 31, k Ниблэка = 0.2, k Сауволы = 0.2, R = 128.", "",
             "IoU — доля пересечения найденного текста и эталонной маски в их объединении. Больше — лучше. Текстом считаются чёрные пиксели.", "",
             "| Изображение | Ниблэк, IoU | Саувола, IoU |", "|---|---:|---:|"]
    for name in ("shadow_text.png", "faint_text.png"):
        scores = []
        for output in local_thresholds(read_image(samples / name)):
            foreground = output == 0
            scores.append(np.count_nonzero(foreground & truth) / np.count_nonzero(foreground | truth))
        lines.append(f"| {name} | {scores[0]:.4f} | {scores[1]:.4f} |")
    lines += ["", "На тексте с тенью Саувола подавляет шум фона. На бледном тексте порог Сауволы слишком низкий: штрихи сливаются с фоном, а Ниблэк их сохраняет.", "",
              "## Резкость", "", "Лаплас: коэффициент 0.6. Нерезкое маскирование: коэффициент 1.5, σ = 1.2.", "",
              "MSE — средний квадрат разности с `sharp_reference.png` по всем RGB-компонентам. Меньше — лучше. Эта метрика измеряет сходство с известным оригиналом, а не субъективную резкость.", "",
              "| Изображение | До обработки, MSE | Лаплас, MSE | Маскирование, MSE |", "|---|---:|---:|---:|"]
    reference = read_image(samples / "sharp_reference.png").astype(float)
    for name in ("blurred_shapes.png", "noisy_shapes.png"):
        image = read_image(samples / name)
        scores = [np.mean((output.astype(float) - reference) ** 2)
                  for output in (image, laplacian_sharpen(image), unsharp_mask(image))]
        lines.append(f"| {name} | {scores[0]:.2f} | {scores[1]:.2f} | {scores[2]:.2f} |")
    lines += ["", "На размытом изображении оба метода уменьшают ошибку. На зашумлённом ошибка растёт: фильтры усиливают не только границы, но и шум. Вывод относится к этим изображениям и выбранным параметрам.", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    report = build_report()
    (Path(__file__).resolve().parent / "samples" / "RESULTS.md").write_text(report, encoding="utf-8")
    print(report)
