#!/usr/bin/env python3
"""Render the social preview from the homepage copy and ASCII artwork.

    uv run --locked tools/og_image.py
"""

from html.parser import HTMLParser
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont
import yaml

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "tools" / "sources" / "fonts"
OUT = ROOT / "static" / "assets" / "branding" / "og-homepage-v2.png"
W, H = 1200, 630
VOID = (16, 16, 20)
PRIMARY = (230, 225, 214)
SECONDARY = (146, 144, 154)
LAVENDER = (180, 163, 230)
BORDER = (52, 49, 61)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


class HomepageText(HTMLParser):
    """Keep text and the homepage's accent colors when reading its HTML."""

    def __init__(self):
        super().__init__()
        self.parts = []
        self.color = PRIMARY

    def handle_starttag(self, tag, attrs):
        style = dict(attrs).get("class", "")
        self.color = {"aa-hi": LAVENDER, "aa-lo": SECONDARY}.get(style, PRIMARY)

    def handle_endtag(self, tag):
        self.color = PRIMARY

    def handle_data(self, data):
        self.parts.append((data, self.color))


def plain_text(html):
    parser = HomepageText()
    parser.feed(html)
    return " ".join("".join(text for text, _ in parser.parts).split())


def main() -> None:
    site = yaml.safe_load((ROOT / "data/site.yaml").read_text())
    img = Image.new("RGB", (W, H), VOID)
    draw = ImageDraw.Draw(img)
    serif = font("InstrumentSerif-Regular.ttf", 48)
    mono = font("IBMPlexMono-Regular.ttf", 17)
    x = 48
    for text, color in [("pr", PRIMARY), ("λ", LAVENDER), ("tam", PRIMARY)]:
        word_font = font("JetBrainsMono-Medium.ttf", 41) if text == "λ" else serif
        draw.text((x, 17), text, font=word_font, fill=color)
        x += draw.textlength(text, font=word_font)
    draw.text((x + 22, 40), site["name"].lower(), font=mono, fill=SECONDARY)
    draw.text((850, 40), "about  projects  writing", font=font("IBMPlexMono-Regular.ttf", 14), fill=SECONDARY)
    draw.line((0, 84, W, 84), fill=BORDER)

    # Use the exact desktop character composition instead of a different portrait.
    source = (ROOT / "templates/partials/shanks-ascii.html").read_text()
    parser = HomepageText()
    parser.feed(source.split("{% raw %}", 1)[1].split("{% endraw %}", 1)[0])
    art_font = font("IBMPlexMono-Regular.ttf", 8)
    advance = draw.textlength("M", font=art_font)
    x, y = 785, 110
    for text, color in parser.parts:
        for char in text:
            if char == "\n":
                x, y = 785, y + 6.6
            else:
                draw.text((x, y), char, font=art_font, fill=color)
                x += advance
    draw.text((850, 588), "// shanks.asc · utf-8", font=font("IBMPlexMono-Regular.ttf", 12), fill=SECONDARY)

    hello = font("IBMPlexMono-Medium.ttf", 23)
    body = font("IBMPlexMono-Regular.ttf", 19)
    draw.text((48, 206), ">", font=hello, fill=LAVENDER)
    y = 206
    for line in textwrap.wrap(plain_text(site["hero"]["hello"]), width=44):
        draw.text((76, y), line, font=hello, fill=PRIMARY)
        y += 37
    y += 25
    for key in ("machinery", "enjoy"):
        for line in textwrap.wrap(plain_text(site["hero"][key]), width=54):
            draw.text((48, y), line, font=body, fill=SECONDARY)
            y += 31
        y += 23
    draw.text((48, 583), "GitHub   X   LinkedIn   Email", font=mono, fill=SECONDARY)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
