"""Пересоздать рисунки и численные таблицы отчёта из изображений samples/."""

from pathlib import Path
import sys

import numpy as np
from PIL import Image

LAB = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(LAB))
from processing import read_image, local_thresholds, laplacian_sharpen, unsharp_mask


def main():
    output = Path(__file__).resolve().parent
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    samples = LAB / "samples"
    truth = read_image(samples / "text_mask.png")[:, :, 0] == 0
    threshold_rows = []
    for name, label in (("shadow_text", "Текст с тенью"), ("faint_text", "Бледный текст")):
        source = read_image(samples / f"{name}.png")
        results = local_thresholds(source, window=31, niblack_k=0.2, sauvola_k=0.2)
        scores = []
        for method, result in zip(("niblack", "sauvola"), results):
            Image.fromarray(result).save(figures / f"{name}_{method}.png")
            mask = result == 0
            scores.append(np.count_nonzero(mask & truth) / np.count_nonzero(mask | truth))
        threshold_rows.append(f"{label} & {scores[0]:.4f} & {scores[1]:.4f} " + r"\\")

    reference = read_image(samples / "sharp_reference.png").astype(np.float64)
    sharpening_rows = []
    # Один и тот же фрагмент: координаты (left, top, right, bottom) в пикселях.
    crop = (25, 65, 325, 325)
    for name, label in (("blurred_shapes", "Размытие"), ("noisy_shapes", "Шум")):
        source = read_image(samples / f"{name}.png")
        results = (source, laplacian_sharpen(source, 0.6), unsharp_mask(source, 1.5, 1.2))
        scores = []
        for method, result in zip(("source", "laplacian", "unsharp"), results):
            Image.fromarray(result).crop(crop).save(figures / f"{name}_{method}.png")
            scores.append(np.mean((result.astype(np.float64) - reference) ** 2))
        sharpening_rows.append(f"{label} & {scores[0]:.2f} & {scores[1]:.2f} & {scores[2]:.2f} " + r"\\")

    (output / "threshold_table.tex").write_text(
        "\n".join([r"\begin{tabular}{lcc}\toprule",
                    r"Изображение & Ниблэк, IoU & Саувола, IoU \\", r"\midrule",
                    *threshold_rows, r"\bottomrule\end{tabular}"]) + "\n", encoding="utf-8")
    (output / "sharpening_table.tex").write_text(
        "\n".join([r"\begin{tabular}{lrrr}\toprule",
                    r"Искажение & До обработки & Лапласиан & Маскирование \\", r"\midrule",
                    *sharpening_rows, r"\bottomrule\end{tabular}"]) + "\n", encoding="utf-8")
    print("Рисунки и таблицы отчёта обновлены.")


if __name__ == "__main__":
    main()
