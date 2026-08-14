"""Generate the workshop ICO used by Explorer, taskbar and the executable."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "workshop.ico"


def build(size: int = 256) -> Image.Image:
    scale = size / 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    def box(values: tuple[float, float, float, float]):
        return tuple(round(value * scale) for value in values)

    draw.ellipse(
        box((5, 5, 49, 49)),
        fill="#ffb703",
        outline="#e58f00",
        width=max(1, round(2 * scale)),
    )
    draw.ellipse(box((17, 21, 23, 28)), fill="#023047")
    draw.ellipse(box((31, 21, 37, 28)), fill="#023047")
    draw.ellipse(box((22, 34, 31, 41)), fill="#e63946")

    cx, cy, outer, inner = 44, 44, 18, 13
    points = []
    for index in range(24):
        angle = -math.pi / 2 + index * math.pi / 12
        radius = outer if index % 3 != 1 else inner
        points.append(
            (
                round((cx + radius * math.cos(angle)) * scale),
                round((cy + radius * math.sin(angle)) * scale),
            )
        )
    draw.polygon(points, fill="#219ebc", outline="#126782")
    draw.ellipse(box((38, 38, 50, 50)), fill="#e9f5f8")
    draw.ellipse(box((41, 41, 47, 47)), fill="#126782")
    return image


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image = build()
    image.save(
        OUTPUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
