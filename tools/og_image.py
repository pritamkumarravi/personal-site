#!/usr/bin/env python3
"""Render the 1200x630 Open Graph social preview image.

    uv run tools/og_image.py

Output: static/assets/branding/og-image.png.
Uses the Shanks artwork, blended into the background via lighten so its black
base merges with the card's charcoal.
"""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "tools" / "sources" / "fonts"
IMAGES = ROOT / "tools" / "sources" / "images"
OUT = ROOT / "static" / "assets" / "branding" / "og-image.png"

W, H = 1200, 630

VOID = (16, 16, 20)
PRIMARY = (230, 225, 214)
SECONDARY = (146, 144, 154)
MUTED = (101, 97, 108)
LAVENDER = (180, 163, 230)
BORDER = (52, 49, 61)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def draw_tracked(draw: ImageDraw.ImageDraw, xy, text, fnt, fill, tracking=0) -> float:
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking
    return x - tracking


def main() -> None:
    img = Image.new("RGB", (W, H), VOID)

    # --- Shanks, right side; crop to the face, blend via lighten ------------
    art = Image.open(IMAGES / "shanks ascii.png").convert("L")
    crop_h = 1060                                   # face + sword hand
    art = art.crop((0, 0, art.width, min(crop_h, art.height)))
    target_h = H + 60                               # bleed top/bottom
    target_w = round(art.width * target_h / art.height)
    art = art.resize((target_w, target_h), Image.LANCZOS)
    art = art.convert("RGB")

    base_gray = Image.new("RGB", art.size, VOID)
    blended = ImageChops.lighter(base_gray, art)     # black artwork bg -> void
    # fade the left edge so text keeps clean contrast
    mask = Image.new("L", art.size, 255)
    mdraw = ImageDraw.Draw(mask)
    fade = 200
    for x in range(fade):
        mdraw.line([(x, 0), (x, art.height)], fill=int(255 * (x / fade) ** 1.3))
    img.paste(blended, (W - target_w + 20, -30), mask)

    draw = ImageDraw.Draw(img)

    # --- thin frame ----------------------------------------------------------
    inset = 28
    draw.rectangle([inset, inset, W - inset, H - inset], outline=BORDER, width=1)

    meta = font("IBMPlexMono-Regular.ttf", 15)
    draw.text((inset + 22, inset + 16), "~/pritamravi.com", font=meta, fill=MUTED)

    # --- identity block --------------------------------------------------------
    x0 = 84

    # wordmark: pr[lamda]tam — lambda comes from JetBrains Mono
    serif = font("InstrumentSerif-Regular.ttf", 112)
    mono_l = font("JetBrainsMono-Medium.ttf", 92)
    wx = x0
    y0 = 170
    for seg, fnt in [("pr", serif), ("λ", mono_l), ("tam", serif)]:
        draw.text((wx, y0), seg, font=fnt, fill=PRIMARY)
        wx += draw.textlength(seg, font=fnt)
    lam_x = x0 + draw.textlength("pr", font=serif)
    draw.text((lam_x, y0 + 4), "λ", font=mono_l, fill=LAVENDER)

    y = y0 + 160
    draw_tracked(draw, (x0, y), "PRITAM RAVI", font("IBMPlexMono-SemiBold.ttf", 28), PRIMARY, 7)

    y += 58
    draw.text((x0, y), "Building systems. Exploring creative intelligence.",
              font=font("InstrumentSerif-Italic.ttf", 30), fill=SECONDARY)

    y += 62
    draw_tracked(
        draw,
        (x0, y),
        "ML Systems · Inference Engineering · GPU Performance",
        font("IBMPlexMono-Regular.ttf", 18),
        MUTED,
        1,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
