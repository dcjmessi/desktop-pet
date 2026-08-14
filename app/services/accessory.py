"""Prebaked accessory variants.

Following the mainstream desktop-pet approach, an accessory is not stamped at
runtime: every action frame is rendered once with the accessory drawn on it and
stored as its own frame pack, so switching is just a folder swap.

Placement is anchored per frame (head top, head width, eye centers) so the hat
stays on the head while the pose moves.
"""

from __future__ import annotations

import math
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageFilter

Progress = Callable[[str], None]

ACCESSORY_IDS = (
    "acc_hat_beanie",
    "acc_hat_party",
    "acc_hat_crown",
    "acc_glasses_round",
    "acc_glasses_sun",
    "acc_bow",
    "acc_scarf",
    "acc_star_stick",
)


@dataclass
class Anchors:
    left: int
    top: int
    right: int
    bottom: int
    head_left: int
    head_right: int
    head_top: int
    eye_y: int
    eye_left_x: int
    eye_left_y: int
    eye_right_x: int
    eye_right_y: int
    eye_r: int

    @property
    def head_w(self) -> int:
        return max(8, self.head_right - self.head_left)

    @property
    def head_h(self) -> int:
        # chibi heads are about as tall as they are wide; cross-check with eye line
        by_width = self.head_w
        by_eyes = int((self.eye_y - self.head_top) / 0.42) if self.eye_y > self.head_top else by_width
        return max(12, min(by_width, by_eyes))

    @property
    def head_cx(self) -> int:
        return (self.head_left + self.head_right) // 2

    @property
    def neck_y(self) -> int:
        return min(self.bottom - 6, self.head_top + int(self.head_h * 0.95))

    @property
    def head_angle(self) -> float:
        return math.degrees(
            math.atan2(
                self.eye_right_y - self.eye_left_y,
                max(1, self.eye_right_x - self.eye_left_x),
            )
        )


def detect_anchors(img: Image.Image) -> Anchors | None:
    alpha = img.split()[-1]
    bbox = alpha.getbbox()
    if not bbox:
        return None
    left, top, right, bottom = bbox
    height = bottom - top
    px = img.load()
    apx = alpha.load()

    # eye band: dark opaque pixels in the upper head area
    band_top = top + int(height * 0.12)
    band_bottom = top + int(height * 0.48)
    dark: list[tuple[int, int]] = []
    for y in range(band_top, band_bottom):
        for x in range(left, right):
            r, g, b, a = px[x, y]
            if a > 140 and (r * 299 + g * 587 + b * 114) / 1000 < 95:
                dark.append((x, y))

    if len(dark) >= 12:
        xs = [p[0] for p in dark]
        ys = [p[1] for p in dark]
        eye_y = sum(ys) // len(ys)
        mid = (min(xs) + max(xs)) / 2
        lefts = [x for x in xs if x < mid]
        rights = [x for x in xs if x >= mid]
        eye_left_x = sum(lefts) // len(lefts) if lefts else int(mid - 12)
        eye_right_x = sum(rights) // len(rights) if rights else int(mid + 12)
        left_ys = [y for x, y in dark if x < mid]
        right_ys = [y for x, y in dark if x >= mid]
        eye_left_y = sum(left_ys) // len(left_ys) if left_ys else eye_y
        eye_right_y = sum(right_ys) // len(right_ys) if right_ys else eye_y
        eye_r = max(4, (max(xs) - min(xs)) // 8)
    else:
        eye_y = top + int(height * 0.30)
        cx = (left + right) // 2
        eye_left_x = cx - (right - left) // 6
        eye_right_x = cx + (right - left) // 6
        eye_left_y = eye_y
        eye_right_y = eye_y
        eye_r = max(4, (right - left) // 12)

    # head width measured at eye level, plus the widest row above it
    head_left, head_right = right, left
    for y in range(top, min(bottom, eye_y + 4)):
        row_left, row_right = None, None
        for x in range(left, right):
            if apx[x, y] > 60:
                if row_left is None:
                    row_left = x
                row_right = x
        if row_left is not None and row_right is not None:
            if row_right - row_left > head_right - head_left:
                head_left, head_right = row_left, row_right
    if head_right <= head_left:
        head_left, head_right = left, right

    return Anchors(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        head_left=head_left,
        head_right=head_right,
        head_top=top,
        eye_y=eye_y,
        eye_left_x=eye_left_x,
        eye_left_y=eye_left_y,
        eye_right_x=eye_right_x,
        eye_right_y=eye_right_y,
        eye_r=eye_r,
    )


def draw_accessory(img: Image.Image, acc_id: str, anchors: Anchors | None = None) -> Image.Image:
    a = anchors or detect_anchors(img)
    if a is None:
        return img
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    hw, hh = a.head_w, a.head_h
    cx = a.head_cx

    if acc_id == "acc_hat_beanie":
        cap_h = int(hh * 0.40)
        top = a.head_top - int(cap_h * 0.35)
        brim_y = top + cap_h
        left = cx - hw // 2 - 3
        right = cx + hw // 2 + 3
        # A soft contact shadow makes the hat sit on the head instead of
        # reading as a flat sticker.
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse(
            (left - 2, brim_y - 4, right + 2, brim_y + 10),
            fill=(20, 35, 60, 105),
        )
        layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3)))
        # Layered tones give the knitted cap volume.
        d.pieslice(
            (left, top, right, brim_y + cap_h),
            start=180,
            end=360,
            fill=(45, 116, 205, 255),
            outline=(28, 82, 158, 255),
            width=max(2, hw // 35),
        )
        d.pieslice(
            (left + 4, top + 3, right - 4, brim_y + cap_h - 5),
            start=180,
            end=360,
            fill=(76, 160, 244, 255),
        )
        d.arc(
            (left + hw * 0.18, top + 5, right - hw * 0.28, brim_y + cap_h * 0.55),
            195,
            305,
            fill=(155, 213, 255, 210),
            width=max(2, hw // 28),
        )
        brim_h = max(7, cap_h // 3)
        d.rounded_rectangle(
            (left - 3, brim_y - brim_h // 2, right + 3, brim_y + brim_h // 2),
            radius=max(4, brim_h // 2),
            fill=(38, 105, 190, 255),
            outline=(24, 73, 142, 255),
            width=max(1, hw // 45),
        )
        # Ribbing follows the brim and visually wraps around the head.
        for k in range(1, 6):
            x = left + int((right - left) * k / 6)
            d.line(
                (x, brim_y - brim_h // 3, x, brim_y + brim_h // 3),
                fill=(102, 177, 235, 170),
                width=max(1, hw // 55),
            )
        pom_r = max(5, hw // 12)
        d.ellipse(
            (cx - pom_r, top - pom_r, cx + pom_r, top + pom_r),
            fill=(82, 165, 235, 255),
            outline=(28, 82, 158, 255),
            width=2,
        )
        d.ellipse(
            (cx - pom_r // 2, top - pom_r // 2, cx + 1, top + 1),
            fill=(185, 226, 255, 210),
        )
        layer = _add_fabric_texture(layer)

    elif acc_id == "acc_hat_party":
        cone_h = int(hh * 0.62)
        base_y = a.head_top + int(hh * 0.14)
        half = max(10, hw // 4)
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse(
            (cx - half - 5, base_y - 4, cx + half + 5, base_y + 7),
            fill=(40, 25, 35, 100),
        )
        layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(2)))
        d.polygon(
            [(cx, base_y - cone_h), (cx - half, base_y), (cx + half, base_y)],
            fill=(225, 64, 104, 255),
        )
        d.line(
            (cx, base_y - cone_h, cx - half, base_y, cx + half, base_y, cx, base_y - cone_h),
            fill=(148, 38, 73, 255),
            width=max(2, hw // 40),
            joint="curve",
        )
        d.line(
            (cx - 2, base_y - cone_h + 8, cx - half // 2, base_y - 8),
            fill=(255, 156, 178, 190),
            width=max(2, hw // 30),
        )
        for k in range(3):
            y = base_y - int(cone_h * (0.25 + 0.22 * k))
            w = int(half * (1 - (0.25 + 0.22 * k)))
            d.line((cx - w, y, cx + w, y), fill=(255, 220, 90, 255), width=4)
        d.ellipse((cx - 6, base_y - cone_h - 6, cx + 6, base_y - cone_h + 6), fill=(255, 220, 90, 255))

    elif acc_id == "acc_hat_crown":
        band_y = a.head_top + int(hh * 0.16)
        half = max(10, hw // 3)
        spike = int(hh * 0.3)
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse(
            (cx - half - 3, band_y - 2, cx + half + 3, band_y + 9),
            fill=(80, 48, 10, 95),
        )
        layer.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(2)))
        pts = [
            (cx - half, band_y),
            (cx - half, band_y - spike // 2),
            (cx - half // 2, band_y - spike),
            (cx, band_y - spike // 2),
            (cx + half // 2, band_y - spike),
            (cx + half, band_y - spike // 2),
            (cx + half, band_y),
        ]
        d.polygon(
            pts, fill=(250, 191, 42, 255), outline=(151, 96, 12, 255)
        )
        band_h = max(6, spike // 4)
        d.rounded_rectangle(
            (cx - half, band_y, cx + half, band_y + band_h),
            radius=max(2, band_h // 3),
            fill=(235, 153, 24, 255),
            outline=(151, 96, 12, 255),
            width=2,
        )
        d.line(
            (cx - half + 5, band_y + 2, cx + half - 5, band_y + 2),
            fill=(255, 232, 134, 220),
            width=2,
        )
        for x, color in (
            (cx - half // 2, (224, 64, 74, 255)),
            (cx, (75, 150, 238, 255)),
            (cx + half // 2, (80, 190, 114, 255)),
        ):
            rr = max(2, band_h // 4)
            d.ellipse((x - rr, band_y + 2, x + rr, band_y + 2 + rr * 2), fill=color)

    elif acc_id in ("acc_glasses_round", "acc_glasses_sun"):
        r = max(7, int(a.eye_r * 2.1))
        lens = (30, 30, 34, 225) if acc_id == "acc_glasses_sun" else (255, 255, 255, 40)
        outline = (25, 25, 28, 255) if acc_id == "acc_glasses_sun" else (70, 80, 95, 255)
        for ex in (a.eye_left_x, a.eye_right_x):
            d.ellipse((ex - r, a.eye_y - r, ex + r, a.eye_y + r), fill=lens, outline=outline, width=3)
        d.line((a.eye_left_x + r, a.eye_y, a.eye_right_x - r, a.eye_y), fill=outline, width=3)
        d.line((a.eye_left_x - r, a.eye_y, a.head_left - 2, a.eye_y + 3), fill=outline, width=3)
        d.line((a.eye_right_x + r, a.eye_y, a.head_right + 2, a.eye_y + 3), fill=outline, width=3)

    elif acc_id == "acc_bow":
        bx = a.head_right - int(hw * 0.12)
        by = a.head_top + int(hh * 0.12)
        rr = max(7, hw // 10)
        d.ellipse((bx - rr * 2, by - rr, bx, by + rr), fill=(255, 120, 160, 255))
        d.ellipse((bx, by - rr, bx + rr * 2, by + rr), fill=(255, 120, 160, 255))
        d.ellipse((bx - rr // 2, by - rr // 2, bx + rr // 2, by + rr // 2), fill=(230, 80, 130, 255))

    elif acc_id == "acc_scarf":
        y = a.neck_y
        half = max(10, int(hw * 0.40))
        band = max(8, int(hh * 0.14))
        d.rounded_rectangle(
            (cx - half, y - band // 2, cx + half, y + band // 2),
            radius=band // 2,
            fill=(60, 200, 130, 255),
            outline=(38, 160, 100, 255),
        )
        # hanging end on the character's left side
        tail_w = max(8, band)
        d.rounded_rectangle(
            (cx - half + 2, y + band // 3, cx - half + 2 + tail_w, y + band // 3 + int(hh * 0.34)),
            radius=tail_w // 2,
            fill=(45, 176, 112, 255),
        )

    elif acc_id == "acc_star_stick":
        hy = a.top + int((a.bottom - a.top) * 0.58)
        hx = a.right + 2
        tip_x, tip_y = hx + 10, hy - int(hh * 0.75)
        d.line((hx - 6, hy + 6, tip_x, tip_y), fill=(176, 128, 72, 255), width=6)
        _star(d, tip_x, tip_y, max(11, hw // 6), (255, 214, 64, 255))
        _star(d, tip_x, tip_y, max(5, hw // 12), (255, 246, 190, 255))

    if acc_id in {
        "acc_hat_beanie",
        "acc_hat_party",
        "acc_hat_crown",
        "acc_glasses_round",
        "acc_glasses_sun",
        "acc_bow",
    } and abs(a.head_angle) > 1.5:
        # Follow head tilt per frame. This is what makes a prebaked accessory
        # feel worn by the character instead of pinned to the screen.
        layer = layer.rotate(
            -a.head_angle,
            resample=Image.Resampling.BICUBIC,
            center=(cx, a.eye_y),
        )
    return Image.alpha_composite(img, layer)


def _add_fabric_texture(layer: Image.Image) -> Image.Image:
    """Blend subtle deterministic fibres into a hat without hard sticker edges."""
    alpha = layer.split()[-1]
    noise = Image.effect_noise(layer.size, 24).point(
        lambda value: max(0, min(38, abs(value - 128) // 2))
    )
    texture_alpha = ImageChops.multiply(alpha, noise)
    texture = Image.new("RGBA", layer.size, (225, 240, 255, 0))
    texture.putalpha(texture_alpha)
    softened = layer.filter(ImageFilter.GaussianBlur(0.28))
    return Image.alpha_composite(softened, texture)


def _star(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int, fill) -> None:
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d.polygon(pts, fill=fill)


def bake_variant(
    actions_root: Path,
    variant_root: Path,
    acc_id: str,
    progress: Progress | None = None,
    anchor_cache: dict[Path, Anchors | None] | None = None,
) -> int:
    """Render every frame of every action with the accessory drawn on."""
    total = 0
    for action_dir in sorted(p for p in actions_root.iterdir() if p.is_dir()):
        dest = variant_root / action_dir.name
        dest.mkdir(parents=True, exist_ok=True)
        for old in dest.glob("*.png"):
            old.unlink()
        for frame_path in sorted(action_dir.glob("*.png")):
            if acc_id == "acc_none":
                shutil.copy2(frame_path, dest / frame_path.name)
                total += 1
                continue
            img = Image.open(frame_path).convert("RGBA")
            if anchor_cache is None:
                anchors = detect_anchors(img)
            else:
                if frame_path not in anchor_cache:
                    anchor_cache[frame_path] = detect_anchors(img)
                anchors = anchor_cache[frame_path]
            out = draw_accessory(img, acc_id, anchors)
            out.save(dest / frame_path.name, "PNG", compress_level=1)
            total += 1
    if progress:
        progress(f"{acc_id}: {total} 帧")
    return total


def bake_all_variants(
    actions_root: Path,
    variants_root: Path,
    progress: Progress | None = None,
) -> list[str]:
    # Detect landmarks once. Rendering variants then runs in parallel because
    # every output folder is independent.
    cache: dict[Path, Anchors | None] = {}
    for action_dir in sorted(p for p in actions_root.iterdir() if p.is_dir()):
        for frame_path in sorted(action_dir.glob("*.png")):
            with Image.open(frame_path) as source:
                cache[frame_path] = detect_anchors(source.convert("RGBA"))

    baked = ["acc_none"]
    bake_variant(actions_root, variants_root / "acc_none", "acc_none", progress, cache)
    with ThreadPoolExecutor(max_workers=min(4, len(ACCESSORY_IDS))) as pool:
        jobs = [
            pool.submit(
                bake_variant,
                actions_root,
                variants_root / acc_id,
                acc_id,
                progress,
                cache,
            )
            for acc_id in ACCESSORY_IDS
        ]
        for acc_id, job in zip(ACCESSORY_IDS, jobs):
            job.result()
            baked.append(acc_id)
    return baked
