#!/usr/bin/env python3
"""Convert an image to ASCII art for the site.

    uv run tools/ascii_art.py tools/sources/images/blackhole.jpg \
        --width 68 --charset ascii --gamma 1.1 --invert

This standalone converter writes to stdout by default. Use --out to save a
rendered text file. The homepage Shanks artwork uses the dedicated
tools/generate_shanks_ascii.py workflow instead.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

RAMPS = {
    # dark -> light, 10-step classic
    "ascii": " .:-=+*#%@",
    # finer 18-step for photographic sources
    "fine": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    # half-block + shade characters (needs Unicode-capable face, e.g. JetBrains Mono)
    "blocks": " ░▒▓█",
}


def render(
    src: Path,
    width: int,
    charset: str = "ascii",
    gamma: float = 1.0,
    contrast: float = 1.0,
    invert: bool = False,
    aspect: float = 0.5,
    sampling: str = "lanczos",
) -> str:
    ramp = RAMPS[charset]
    img = Image.open(src).convert("L")
    img = ImageOps.autocontrast(img, cutoff=1)
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)

    w = width
    h = max(1, round(img.height / img.width * w * aspect))
    img = img.resize((w, h), Image.NEAREST if sampling == "nearest" else Image.LANCZOS)

    lines = []
    lut = [min(len(ramp) - 1, int(((i / 255.0) ** gamma) * len(ramp))) for i in range(256)]
    if invert:  # for light backgrounds: map bright pixels to dense chars
        lut = [len(ramp) - 1 - v for v in lut]
    px = img.load()
    for y in range(h):
        lines.append("".join(ramp[lut[px[x, y]]] for x in range(w)))
    text = "\n".join(line.rstrip() for line in lines)
    return text.strip("\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image", type=Path)
    ap.add_argument("--width", type=int, default=64, help="columns of output")
    ap.add_argument("--charset", choices=RAMPS, default="ascii")
    ap.add_argument("--gamma", type=float, default=1.0, help="<1 brightens, >1 darkens")
    ap.add_argument("--contrast", type=float, default=1.0)
    ap.add_argument("--invert", action="store_true", help="invert tone mapping")
    ap.add_argument("--aspect", type=float, default=0.5, help="cell height/width ratio of the target font")
    ap.add_argument("--sampling", choices=["lanczos", "nearest"], default="lanczos",
                    help="nearest preserves thin bright streaks; lanczos is smoother")
    ap.add_argument("--out", type=Path, default=None, help="write to file instead of stdout")
    args = ap.parse_args()

    art = render(
        args.image, args.width, args.charset, args.gamma, args.contrast, args.invert,
        args.aspect, args.sampling,
    )
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(art + "\n", encoding="utf-8")
        print(f"wrote {args.out} ({art.count(chr(10)) + 1} rows x {args.width} cols)")
    else:
        print(art)


if __name__ == "__main__":
    main()
