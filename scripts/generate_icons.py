#!/usr/bin/env python3
"""Export Ledger mark PNGs and favicon from static/icons/ledger-mark.svg."""

from __future__ import annotations

import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_PATH = os.path.join(ROOT, "static", "icons", "ledger-mark.svg")
OUT_DIR = os.path.join(ROOT, "static", "icons")
LOGO_PATH = os.path.join(ROOT, "static", "logo.png")

SIZES = (16, 32, 48, 180, 192, 512, 1024)


def main() -> int:
    try:
        import cairosvg
    except ImportError:
        print("Install cairosvg: pip install cairosvg", file=sys.stderr)
        return 1

    from PIL import Image

    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.isfile(SVG_PATH):
        print(f"Missing {SVG_PATH}", file=sys.stderr)
        return 1

    with open(SVG_PATH, "rb") as f:
        svg_bytes = f.read()

    png_by_size: dict[int, bytes] = {}
    for size in SIZES:
        png = cairosvg.svg2png(bytestring=svg_bytes, output_width=size, output_height=size)
        png_by_size[size] = png
        if size in (180, 192, 512, 1024):
            out_name = f"icon-{size}.png" if size != 1024 else "icon-1024.png"
            out_path = os.path.join(OUT_DIR, out_name)
            with open(out_path, "wb") as out:
                out.write(png)
            print(f"Wrote {out_path}")

    logo_png = cairosvg.svg2png(bytestring=svg_bytes, output_width=72, output_height=72)
    with open(LOGO_PATH, "wb") as out:
        out.write(logo_png)
    print(f"Wrote {LOGO_PATH}")

    ico_images = []
    for size in (16, 32, 48):
        img = Image.open(io.BytesIO(png_by_size[size])).convert("RGBA")
        ico_images.append(img)
    ico_path = os.path.join(ROOT, "static", "favicon.ico")
    ico_images[0].save(
        ico_path,
        format="ICO",
        sizes=[(img.width, img.height) for img in ico_images],
        append_images=ico_images[1:],
    )
    print(f"Wrote {ico_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
