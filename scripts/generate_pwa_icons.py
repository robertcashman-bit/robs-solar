#!/usr/bin/env python3
"""Generate PWA icons for Rob's Finance (emerald wallet on dark background)."""

from __future__ import annotations

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover - dev utility
    raise SystemExit("Install Pillow: pip install pillow") from exc

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "icons"
BG = (12, 15, 20, 255)
EMERALD = (16, 185, 129, 255)
TEAL = (20, 184, 166, 255)
EMERALD_GLOW = (52, 211, 153, 120)
WHITE = (255, 255, 255, 255)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)

    corner = size * 0.18
    inset = size * 0.14
    glow_inset = inset - size * 0.03
    draw.rounded_rectangle(
        (glow_inset, glow_inset, size - glow_inset, size - glow_inset),
        radius=corner + size * 0.04,
        fill=EMERALD_GLOW,
    )

    for y in range(int(inset), int(size - inset)):
        t = (y - inset) / max(1, size - 2 * inset)
        r = int(_lerp(EMERALD[0], TEAL[0], t))
        g = int(_lerp(EMERALD[1], TEAL[1], t))
        b = int(_lerp(EMERALD[2], TEAL[2], t))
        draw.line((inset, y, size - inset, y), fill=(r, g, b, 255))

    draw.rounded_rectangle(
        (inset, inset, size - inset, size - inset),
        radius=corner,
        outline=(255, 255, 255, 40),
        width=max(1, size // 128),
    )

    wallet_top = size * 0.36
    wallet_bottom = size * 0.72
    wallet_left = size * 0.28
    wallet_right = size * 0.72
    draw.rounded_rectangle(
        (wallet_left, wallet_top, wallet_right, wallet_bottom),
        radius=size * 0.06,
        fill=(255, 255, 255, 235),
    )
    clasp_h = (wallet_bottom - wallet_top) * 0.35
    draw.rounded_rectangle(
        (wallet_right - size * 0.14, wallet_top + (wallet_bottom - wallet_top - clasp_h) / 2,
         wallet_right + size * 0.02, wallet_top + (wallet_bottom - wallet_top + clasp_h) / 2),
        radius=size * 0.03,
        fill=EMERALD,
    )

    font_size = int(size * 0.34)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
        except OSError:
            font = ImageFont.load_default()

    symbol = "£"
    bbox = draw.textbbox((0, 0), symbol, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = (size - text_w) / 2 - bbox[0]
    text_y = wallet_top + (wallet_bottom - wallet_top - text_h) / 2 - bbox[1] - size * 0.02
    draw.text((text_x, text_y), symbol, fill=TEAL, font=font)

    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (180, 192, 512):
        draw_icon(size).save(OUT / f"icon-{size}.png", format="PNG")
    draw_icon(32).save(ROOT / "frontend" / "public" / "favicon.png", format="PNG")
    print(f"Wrote icons to {OUT}")


if __name__ == "__main__":
    main()
