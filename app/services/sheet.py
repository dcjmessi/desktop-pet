"""Slice Codex-format sprite atlases into PetPack action frames.

The atlas rows carry real poses, so actions map to rows instead of being faked by
transforming a single portrait. Actions the atlas has no row for (sleep with ZZZ,
eating with food, vanish/appear puffs) are composed on top of the closest real pose.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Iterable

from PIL import Image, ImageDraw

Progress = Callable[[str], None]

CELL = (192, 208)

# Row semantics of the Codex v1 (9 rows) / v2 (11 rows) atlas, verified visually
# against the reference sheets: 0 idle, 1/2 running, 3 waving, 4 jumping,
# 5 sad/hurt, 6 hands-to-mouth happy, 7 calm waiting, 8 thinking, 9 talking.
ROW_SOURCES: dict[str, int] = {
    "idle": 0,
    "walk_r": 1,
    "walk_l": 2,
    "wave": 3,
    "jump": 4,
    "dance": 4,
    "hit": 5,
    "eat": 6,
    "shy": 6,
    "think": 8,
}

MIRROR_ACTIONS = {"walk_l"}


def _cells(sheet: Image.Image, row: int) -> list[Image.Image]:
    cw, ch = CELL
    cols = sheet.width // cw
    rows = sheet.height // ch
    row = min(max(row, 0), max(0, rows - 1))
    out: list[Image.Image] = []
    for col in range(cols):
        cell = sheet.crop((col * cw, row * ch, (col + 1) * cw, (row + 1) * ch))
        if cell.split()[-1].getbbox() is None:
            continue
        out.append(cell)
    return out


def _dark_pixels(img: Image.Image, y0: float, y1: float) -> int:
    """Count dark opaque pixels in a horizontal band — eyes read as dark here."""
    w, h = img.size
    top, bottom = int(h * y0), int(h * y1)
    px = img.load()
    count = 0
    for y in range(top, bottom):
        for x in range(0, w, 2):
            r, g, b, a = px[x, y]
            if a > 128 and (r * 299 + g * 587 + b * 114) / 1000 < 90:
                count += 1
    return count


def closed_eye_frame(candidates: Iterable[Image.Image]) -> Image.Image | None:
    """Pick a front-facing frame whose eyes read as closed.

    Closed eyes mean fewer dark pixels in the eye band, but a pet that turned away
    also loses them — so frames much smaller than the typical silhouette are skipped.
    """
    items = list(candidates)
    if not items:
        return None
    areas = [_opaque_area(img) for img in items]
    ordered = sorted(areas)
    median = ordered[len(ordered) // 2] or 1
    best: tuple[float, Image.Image] | None = None
    for img, area in zip(items, areas):
        if area < median * 0.85:
            continue
        score = _dark_pixels(img, 0.16, 0.52) / area
        if best is None or score < best[0]:
            best = (score, img)
    return best[1] if best else items[0]


def _opaque_area(img: Image.Image) -> int:
    hist = img.split()[-1].histogram()
    return sum(hist[140:])


def _pad(img: Image.Image, pad_top: int = 0, pad_x: int = 0) -> Image.Image:
    canvas = Image.new("RGBA", (img.width + pad_x * 2, img.height + pad_top), (0, 0, 0, 0))
    canvas.alpha_composite(img, (pad_x, pad_top))
    return canvas


def _shift(img: Image.Image, dx: int, dy: int) -> Image.Image:
    canvas = Image.new("RGBA", img.size, (0, 0, 0, 0))
    canvas.alpha_composite(img, (max(0, dx), max(0, dy)))
    return canvas


def _rotate(img: Image.Image, angle: float) -> Image.Image:
    rotated = img.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    canvas = Image.new("RGBA", img.size, (0, 0, 0, 0))
    canvas.alpha_composite(
        rotated,
        ((img.width - rotated.width) // 2, img.height - rotated.height),
    )
    return canvas


def _content_box(img: Image.Image) -> tuple[int, int, int, int]:
    bbox = img.split()[-1].getbbox()
    return bbox or (0, 0, img.width, img.height)


def compose_sleep(sources: list[Image.Image], frames: int = 8) -> list[Image.Image]:
    """Lying-down drowsy loop with rising ZZZ, built from a closed-eye pose."""
    base = closed_eye_frame(sources) or sources[0]
    out: list[Image.Image] = []
    for i in range(frames):
        t = i / frames
        img = _pad(base.copy(), pad_top=34, pad_x=18)
        # slumped over, squashed down, breathing slowly
        img = _squash(img, 1.06, 0.86 - 0.02 * math.sin(t * math.tau))
        img = _rotate(img, 30 + 4 * math.sin(t * math.tau))
        img = _shift(img, 0, int(6 + 3 * math.sin(t * math.tau)))
        d = ImageDraw.Draw(img)
        x0, y0, x1, _ = _content_box(img)
        # three Z's drifting up-right, staggered
        for k in range(3):
            phase = (t + k / 3) % 1.0
            size = 13 + k * 5
            zx = x1 - 24 + int(16 * phase) + k * 9
            zy = int(30 - 26 * phase) + k * 2
            alpha = int(235 * (1 - phase))
            d.text((zx, zy), "Z", fill=(74, 144, 226, alpha), font_size=size)
        out.append(img)
    return out


def compose_eat(sources: list[Image.Image], frames: int = 8) -> list[Image.Image]:
    """Chewing loop from the hands-to-mouth row plus a drumstick that gets eaten."""
    out: list[Image.Image] = []
    n = max(1, len(sources))
    for i in range(frames):
        t = i / frames
        base = sources[i % n]
        img = _pad(base.copy(), pad_top=34, pad_x=10)
        # chewing bob
        img = _shift(img, 0, int(2 + 2 * math.sin(t * math.tau * 2)))
        d = ImageDraw.Draw(img)
        bx0, by0, bx1, by1 = _content_box(img)
        body_h = by1 - by0
        # hold the drumstick beside the muzzle, never covering the face
        fx = bx1 - int((bx1 - bx0) * 0.16)
        fy = by0 + int(body_h * 0.40)
        bite = 1.0 - 0.6 * t
        r = max(4, int(13 * bite))
        d.line((fx + r - 2, fy + r, fx + r + 14, fy + r + 16), fill=(246, 240, 224, 255), width=6)
        d.ellipse(
            (fx + r + 9, fy + r + 11, fx + r + 20, fy + r + 22), fill=(246, 240, 224, 255)
        )
        d.ellipse(
            (fx - r, fy - r, fx + r, fy + r), fill=(206, 128, 62, 255), outline=(146, 86, 36, 255)
        )
        if i % 2 == 0:
            for k in range(3):
                px_ = fx - 18 - k * 6
                py_ = fy + 16 + (k % 2) * 6
                d.ellipse((px_, py_, px_ + 3, py_ + 3), fill=(206, 128, 62, 210))
        out.append(img)
    return out


def compose_vanish(sources: list[Image.Image], frames: int = 8) -> list[Image.Image]:
    base = sources[0]
    out: list[Image.Image] = []
    for i in range(frames):
        t = i / max(1, frames - 1)
        img = _pad(base.copy(), pad_top=34, pad_x=16)
        shrunk = _scale_from_bottom(img, 1.0 - 0.45 * t)
        alpha = int(255 * (1 - t) ** 0.8)
        shrunk.putalpha(shrunk.split()[-1].point(lambda a, m=alpha: min(a, m)))
        d = ImageDraw.Draw(shrunk)
        bx0, by0, bx1, by1 = _content_box(img)
        cx, cy = (bx0 + bx1) // 2, (by0 + by1) // 2
        for k in range(4):
            rr = int(16 + 40 * t) + k * 9
            fade = max(0, int(190 * (1 - t)) - k * 30)
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(226, 226, 232, fade), width=4)
        out.append(shrunk)
    return out


def compose_appear(sources: list[Image.Image], frames: int = 8) -> list[Image.Image]:
    return list(reversed(compose_vanish(sources, frames)))


def _squash(img: Image.Image, sx: float, sy: float) -> Image.Image:
    w, h = img.size
    nw, nh = max(1, int(w * sx)), max(1, int(h * sy))
    scaled = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.alpha_composite(scaled, ((w - nw) // 2, h - nh))
    return canvas


def _scale_from_bottom(img: Image.Image, scale: float) -> Image.Image:
    w, h = img.size
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    scaled = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.alpha_composite(scaled, ((w - nw) // 2, h - nh))
    return canvas


def _decorate_row_action(action: str, frames: list[Image.Image]) -> list[Image.Image]:
    """Pad every row-sourced action the same way so frames stay aligned."""
    out: list[Image.Image] = []
    for i, frame in enumerate(frames):
        img = _pad(frame.copy(), pad_top=34, pad_x=10)
        if action in MIRROR_ACTIONS:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if action == "hit":
            # add an impact flash and a wobble on the first frames
            t = i / max(1, len(frames) - 1)
            img = _rotate(img, -14 * math.sin(t * math.pi * 2))
            if i < 2:
                d = ImageDraw.Draw(img)
                bx0, by0, bx1, _ = _content_box(img)
                cx = (bx0 + bx1) // 2
                for k in range(3):
                    ang = -0.6 + k * 0.6
                    x = cx + int(34 * math.cos(ang))
                    y = by0 + 6 + int(10 * math.sin(ang))
                    d.line((x, y, x + int(12 * math.cos(ang)), y - 12), fill=(255, 96, 96, 235), width=4)
        elif action == "dance":
            t = i / max(1, len(frames))
            img = _rotate(img, 12 * math.sin(t * math.tau))
        elif action == "shy":
            d = ImageDraw.Draw(img)
            bx0, by0, bx1, by1 = _content_box(img)
            blush_y = by0 + int((by1 - by0) * 0.26)
            span = (bx1 - bx0) // 2
            for sign in (-1, 1):
                cx = (bx0 + bx1) // 2 + sign * int(span * 0.62)
                d.ellipse((cx - 9, blush_y - 5, cx + 9, blush_y + 5), fill=(255, 130, 150, 130))
        elif action == "think":
            d = ImageDraw.Draw(img)
            bx0, by0, bx1, _ = _content_box(img)
            step = i % 3
            for k in range(step + 1):
                rr = 4 + k * 3
                x = bx1 - 18 + k * 10
                y = 26 - k * 9
                d.ellipse((x, y, x + rr * 2, y + rr * 2), fill=(255, 255, 255, 210), outline=(150, 160, 175, 220))
        out.append(img)
    return out


def build_actions_from_sheet(
    sheet_path: Path,
    actions_root: Path,
    progress: Progress | None = None,
) -> dict[str, int]:
    """Write every action folder from one atlas. Returns action -> frame count."""
    sheet = Image.open(sheet_path).convert("RGBA")
    counts: dict[str, int] = {}
    rows_cache: dict[int, list[Image.Image]] = {}

    def row(idx: int) -> list[Image.Image]:
        if idx not in rows_cache:
            rows_cache[idx] = _cells(sheet, idx)
        return rows_cache[idx] or _cells(sheet, 0)

    for action, row_idx in ROW_SOURCES.items():
        frames = _decorate_row_action(action, row(row_idx))
        counts[action] = _write(actions_root / action, frames)
        if progress:
            progress(f"{action}: {counts[action]} 帧")

    # sleep from the calmest closed-eye poses across the drowsy/thinking rows
    sleep_pool = row(8) + row(5) + row(7)
    counts["sleep"] = _write(actions_root / "sleep", compose_sleep(sleep_pool))
    counts["eat"] = _write(actions_root / "eat", compose_eat(row(6)))
    counts["vanish"] = _write(actions_root / "vanish", compose_vanish(row(0)))
    counts["appear"] = _write(actions_root / "appear", compose_appear(row(0)))
    if progress:
        progress("sleep / eat / vanish / appear 已合成")
    return counts


def _write(folder: Path, frames: list[Image.Image]) -> int:
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    for i, frame in enumerate(frames):
        frame.save(folder / f"{i:02d}.png")
    return len(frames)


def tint_sheet(sheet_path: Path, out_path: Path, rgb: tuple[int, int, int], strength: float = 0.55) -> Path:
    """Recolor an atlas so recolored stand-in pets keep the real animation."""
    img = Image.open(sheet_path).convert("RGBA")
    r, g, b, a = img.split()
    r = r.point(lambda v: min(255, int(v * (1 - strength) + rgb[0] * strength)))
    g = g.point(lambda v: min(255, int(v * (1 - strength) + rgb[1] * strength)))
    b = b.point(lambda v: min(255, int(v * (1 - strength) + rgb[2] * strength)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.merge("RGBA", (r, g, b, a)).save(out_path)
    return out_path
