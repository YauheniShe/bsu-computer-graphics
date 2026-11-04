"""Воспроизводимая база примеров. Запуск: python make_samples.py."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter


SAMPLES = Path(__file__).resolve().parent / "samples"


def save_array(name, array):
    Image.fromarray(np.rint(array).clip(0, 255).astype(np.uint8)).save(SAMPLES / name)


def make_samples():
    SAMPLES.mkdir(exist_ok=True)
    rng = np.random.default_rng(13)
    width, height = 720, 480
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.text((42, 32), "IMAGE PROCESSING", fill=255, font=ImageFont.load_default(size=42))
    for y, text in ((122, "Local thresholding"), (188, "A different threshold"),
                    (254, "for every pixel"), (354, "0123456789   Aa Bb Cc")):
        draw.text((44, y), text, fill=255, font=ImageFont.load_default(size=36))
    ink = np.asarray(mask, dtype=np.float64) / 255
    truth = np.where(ink >= 0.5, 0, 255).astype(np.uint8)
    save_array("text_mask.png", truth)

    y, x = np.mgrid[:height, :width]
    background = 235 - 125 * np.exp(-((x - 180) / 190) ** 2) + 8 * y / height
    shadow = background * (1 - ink) + (background - 85) * ink
    shadow += rng.normal(0, 3, shadow.shape)
    save_array("shadow_text.png", shadow)
    # Без шума: слабый текст всего на 22 уровня темнее однородного фона.
    save_array("faint_text.png", 220 - 22 * ink)

    scene = Image.new("RGB", (width, height), (225, 229, 236))
    draw = ImageDraw.Draw(scene)
    draw.rectangle((35, 35, 300, 210), fill=(55, 98, 175))
    draw.ellipse((355, 35, 660, 260), fill=(210, 98, 63))
    draw.polygon(((400, 430), (540, 275), (680, 430)), fill=(58, 135, 100))
    draw.text((65, 85), "DETAIL", fill="white", font=ImageFont.load_default(size=46))
    for x_line in range(40, 310, 12):
        draw.line((x_line, 270, x_line, 430), fill=(45, 50, 60), width=3)
    draw.line((35, 245, 310, 245), fill=(45, 50, 60), width=2)
    scene.save(SAMPLES / "sharp_reference.png")
    scene.filter(ImageFilter.GaussianBlur(radius=1.5)).save(SAMPLES / "blurred_shapes.png")
    noisy = np.asarray(scene, dtype=np.float64) + rng.normal(0, 9, (height, width, 3))
    save_array("noisy_shapes.png", noisy)


if __name__ == "__main__":
    make_samples()
    print(f"Примеры сохранены в {SAMPLES}")
