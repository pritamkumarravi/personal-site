#!/usr/bin/env python3
"""Convert source TTF fonts to subsetted WOFF2 for web delivery.

Subsets to Latin + Greek (lambda) + punctuation + typographic symbols +
arrows/box-drawing (mono faces only). Run from the project root:

    uv run tools/fonts.py
"""

from pathlib import Path

from fontTools import subset

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "sources" / "fonts"
OUT = ROOT / "static" / "assets" / "fonts"
FONTS = [
    "InstrumentSerif-Regular",
    "InstrumentSerif-Italic",
    "IBMPlexMono-Regular",
    "IBMPlexMono-Medium",
    "IBMPlexMono-SemiBold",
    "JetBrainsMono-Regular",
    "JetBrainsMono-Medium",
    "JetBrainsMono-Bold",
]

# Latin + punctuation shared by every face.
BASE_UNICODE = (
    "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,"
    "U+0304,U+0308,U+0329,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,"
    "U+2212,U+2215,U+FEFF,U+FFFD"
)
# Wordmark lambda lives in the mono faces; serif faces stay Latin-only.
GREEK = ",U+0370-03FF"
# JetBrains Mono is used for terminal-flavoured UI: arrows + box drawing + blocks.
TERMINAL = ",U+2190-21FF,U+2500-259F,U+25A0-25FF"


def convert(name: str) -> None:
    args = [
        f"{SRC / (name + '.ttf')}",
        f"--output-file={OUT / (name + '.woff2')}",
        "--flavor=woff2",
        f"--unicodes={BASE_UNICODE}{GREEK if name.startswith(('IBM', 'Jet')) else ''}"
        f"{TERMINAL if name.startswith('Jet') else ''}",
        "--layout-features=*",
        "--name-IDs=*",
        "--hinting",
    ]
    subset.main(args)


def main() -> None:
    for name in FONTS:
        convert(name)
        size = (OUT / (name + ".woff2")).stat().st_size
        print(f"  {name}.woff2  {size / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
