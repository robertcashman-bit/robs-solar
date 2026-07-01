#!/usr/bin/env python3
"""Generate PWA icons for Rob's Solar (amber sun on dark background)."""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover - dev utility
    raise SystemExit("Install Pillow: pip install pillow") from exc

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "public" / "icons"
BG = (12, 15, 20, 255)
AMBER = (245, 158, 11, 255)
AMBER_GLOW = (251, 191, 36, 180)


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)
    margin = size * 0.12
    glow = margin * 0.35
    draw.ellipse(
        (margin - glow, margin - glow, size - margin + glow, size - margin + glow),
        fill=AMBER_GLOW,
    )
    draw.ellipse((margin, margin, size - margin, size - margin), fill=AMBER)
    ray_len = size * 0.08
    center = size / 2
    outer = size / 2 - margin * 0.35
    for angle in range(0, 360, 45):
        import math

        rad = math.radians(angle)
        x1 = center + math.cos(rad) * outer
        y1 = center + math.sin(rad) * outer
        x2 = center + math.cos(rad) * (outer + ray_len)
        y2 = center + math.sin(rad) * (outer + ray_len)
        draw.line((x1, y1, x2, y2), fill=AMBER, width=max(2, size // 64))
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        draw_icon(size).save(OUT / f"icon-{size}.png", format="PNG")
    print(f"Wrote icons to {OUT}")


if __name__ == "__main__":
    main()
