#!/usr/bin/env python3
"""Render the Shanks hero as genuine character-based ASCII art.

    uv run tools/generate_shanks_ascii.py

Input   tools/sources/images/original shanks.jpg (736x1308 master)
Output  static/assets/art/shanks.txt               — desktop, plain text asset
        static/assets/art/shanks-mobile.txt        — mobile recomposition
        templates/partials/shanks-ascii.html       — desktop fragment
        templates/partials/shanks-ascii-mobile.html— mobile fragment
        (fragments are included by templates/index.html)

One run writes both compositions: a tall desktop portrait and a tighter,
face-forward mobile crop — the mobile art is recomposed, not squeezed.

Pipeline: crop -> blur -> downsample onto the char grid -> re-normalize ->
tone curve -> density ramp (bright -> dense, so black collapses into
negative space) -> despeckle -> deterministic colouring (lavender on true
speculars, rare phosphor accents). No randomness — same input, same output.

Tuning: --preview-dir out/ writes standalone pages; open them in a browser
while adjusting --crop/--cols/--gamma/--blur/--floor.
"""

from __future__ import annotations

import argparse
import html
import math
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / "sources" / "images" / "original shanks.jpg"

# bright -> dense; the trailing space is the "no ink" cell
RAMP = r"$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

# aspect (height/width) of one monospaced cell in the site's CSS:
# line-height:1, JetBrains Mono advance 0.6em  ->  1.0 / 0.6
CELL_ASPECT = 1.0 / 0.6

# tone bands on the normalized value v = (lum/255)^gamma
BAND_DIM = 0.24      # below: faint residue (muted)
BAND_LO = 0.44       # below: mid shading (secondary), above: primary
BAND_HI = 0.92       # above: lavender highlight


def ramp_for(steps: int) -> str:
    """Evenly subsample the 70-step ramp to ~`steps` tones (space always last).

    Fewer steps = smoother, more legible shading at hero resolution; the
    full ramp reads as noise when neighbouring cells are 1/70th apart.
    """
    if steps >= len(RAMP):
        return RAMP
    sub = RAMP[:: max(1, round(len(RAMP) / steps))]
    if not sub.endswith(" "):
        sub += " "
    return sub


def green_cell(x: int, y: int, permille: int, salt: int = 0) -> bool:
    """Deterministic sparse scatter — no RNG, same picture every run."""
    return ((x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)) % 1000 < permille


def parse_crop(s: str) -> tuple[float, float, float, float]:
    """--crop x0,y0,x1,y1 as fractions of the source frame."""
    try:
        x0, y0, x1, y1 = (float(v) for v in s.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"crop must be x0,y0,x1,y1 — {exc}")
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise argparse.ArgumentTypeError(f"invalid crop {s}")
    return x0, y0, x1, y1


def prepare(crop: tuple[float, float, float, float], cols: int,
            blur_scale: float, black: float, white: float,
            contrast: float, pivot: float, sharpen: int,
            prelocal: int = 0) -> Image.Image:
    """Load, crop, blur away the source's glyph texture, downsample to the
    char grid, and re-normalize at grid resolution."""
    img = Image.open(SRC).convert("L")
    x0, y0, x1, y1 = crop
    img = img.crop((round(x0 * img.width), round(y0 * img.height),
                    round(x1 * img.width), round(y1 * img.height)))
    img = ImageOps.autocontrast(img, cutoff=1)

    # band-limit before downsampling: a light blur stops ink lines aliasing
    # on the char grid. Keep it small — the radius scales with the cell size,
    # and an over-blurred source smears thin features (hair strands, scar
    # lines) into the surrounding tone so they never survive the cell average
    if blur_scale > 0:
        radius = max(0.0, blur_scale * img.width / cols)
        if radius >= 0.3:
            img = img.filter(ImageFilter.GaussianBlur(radius))

    # adaptive local contrast (pre-downsample): a large-radius unsharp at
    # source resolution amplifies feature dips — eye socket, scar lines,
    # sword-guard engraving — BEFORE the cell average can wash them out.
    # Radius scales with the cell so the boost survives the downsampling.
    if prelocal:
        radius = max(1.0, 2.0 * img.width / cols)
        img = img.filter(ImageFilter.UnsharpMask(radius=radius, percent=prelocal, threshold=0))

    rows = max(1, round(img.height / img.width * cols / CELL_ASPECT))
    img = img.resize((cols, rows), Image.LANCZOS)

    # LANCZOS softens the true whites: re-normalize + optionally sharpen
    # at grid resolution. The high cutoff trims specular clipping — without
    # it a few percent of cells pin to 255 and render as flat `$` plates.
    img = ImageOps.autocontrast(img, cutoff=(1, 3))
    lo, hi_pt = int(black * 255), max(int(black * 255) + 1, int(white * 255))
    span = hi_pt - lo
    pv = pivot * 255.0

    def lut(p: int) -> int:
        p = max(0, min(255, (p - lo) * 255 // span))
        # contrast around a pivot in the skin range: feature shadows must
        # fall well below skin density or the face turns to mush
        return max(0, min(255, round(pv + (p - pv) * contrast)))

    img = img.point(lut)
    if sharpen:
        img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=sharpen, threshold=2))
    return img


def clean_border(grid: list[list[tuple[str, str]]]) -> list[list[tuple[str, str]]]:
    """Clear faint cells the frame can reach without crossing solid ink.

    Anything dim/lo that connects to the edge through blanks and other faint
    cells is background residue, not portrait — the eye reads stray glyphs
    floating off the silhouette as noise. Faint texture INSIDE the figure
    (hair strands over the face, shading between dense cells) is enclosed by
    solid ink, so the flood never reaches it.

    Second phase: prune ISOLATED fragments that survive the flood — tiny
    components cut off from the figure in glyph space. Caps keep every real
    fragment safe: sword/hand/guard pieces are dense, solid and far larger
    than the cap, and anything in the lower-right guard zone is left alone
    outright.
    """
    rows, cols = len(grid), len(grid[0])

    def faint(x: int, y: int) -> bool:
        ch, cls = grid[y][x]
        return ch == " " or cls in ("dim", "lo")

    out = [list(row) for row in grid]
    seen = [[False] * cols for _ in range(rows)]
    stack = [(x, y) for x in range(cols) for y in (0, rows - 1)] + \
            [(x, y) for y in range(rows) for x in (0, cols - 1)]
    while stack:
        x, y = stack.pop()
        if not (0 <= x < cols and 0 <= y < rows) or seen[y][x]:
            continue
        seen[y][x] = True
        if not faint(x, y):
            continue
        if out[y][x][0] != " ":
            out[y][x] = (" ", "")
        stack.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))

    # isolated-fragment prune: components are 8-connected by construction, so
    # anything here is already cut off from the figure by blank space. Only
    # specks (≤5 cells) go — hair masses, the eye wedge, sword/hand/guard
    # fragments are far larger — and the lower-right guard zone is skipped.
    inked = [(x, y) for y in range(rows) for x in range(cols) if out[y][x][0] != " "]
    seen = set(inked)
    for cell in inked:
        if cell not in seen:
            continue
        comp, queue = [], [cell]
        seen.discard(cell)
        while queue:
            x, y = queue.pop()
            comp.append((x, y))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if 0 <= n[0] < cols and 0 <= n[1] < rows and n in seen:
                        seen.discard(n)
                        queue.append(n)
        in_guard_zone = min(y for _, y in comp) >= rows * 0.65 and \
            cols * 0.55 <= min(x for x, _ in comp) and \
            max(x for x, _ in comp) <= cols * 0.85
        if len(comp) <= 5 and not in_guard_zone:
            for x, y in comp:
                out[y][x] = (" ", "")
    return out


def grid_from(img: Image.Image, cols: int, gamma: float, floor: float,
              hi_pct: float, steps: int, green_permille: int,
              despeckle: bool, despeckle_passes: int = 1,
              jitter: bool = True, edge_dither: int = 0,
              edges: int = 0, clean_border_on: bool = False
              ) -> list[list[tuple[str, str]]]:
    """Tone-map the prepared image onto the character ramp."""
    rows = img.height
    px = img.load()

    # lavender selection = exactly the top `hi_pct` of *inked* cells by tone.
    # A plain threshold can't hold a share on this source — the jpg's white
    # skin quantizes into huge clusters just below clipping — so take the
    # top-K set outright and break ties with a deterministic hash, which
    # also scatters clipped plateaus instead of clumping them into plates.
    ranked: list[tuple[float, int, int, int]] = []
    for yy in range(rows):
        for xx in range(cols):
            vv = min(1.0, (px[xx, yy] / 255.0) ** gamma)
            if vv >= floor:
                h = (xx * 73856093) ^ (yy * 19349663) ^ (11 * 83492791)
                ranked.append((vv, h, xx, yy))
    ranked.sort(key=lambda t: (t[0], t[1]), reverse=True)
    lavender = {(x, y) for _, _, x, y in ranked[:max(0, int(len(ranked) * hi_pct / 100.0))]}

    ramp = ramp_for(steps)
    n = len(ramp)
    grid: list[list[tuple[str, str]]] = []
    for y in range(rows):
        row = []
        for x in range(cols):
            v = min(1.0, (px[x, y] / 255.0) ** gamma)
            if v < floor:
                row.append((" ", ""))
                continue
            # ramp is ordered dense->light relative to ink: brighter pixel,
            # denser character (v=1 -> "$@B", v=floor -> the trailing space).
            # ±1 step of deterministic jitter breaks up identical-character
            # runs (ordered dithering) — flat `$` fields read as blocks.
            idx = min(n - 1, int((1.0 - v) * n))
            # local gradient (clamped central differences), shared by the
            # edge-aware dither gate and the orientation-glyph pass
            gx = gy = 0
            if edge_dither or edges:
                xl, xr = px[max(0, x - 1), y], px[min(cols - 1, x + 1), y]
                yu, yd = px[x, max(0, y - 1)], px[x, min(rows - 1, y + 1)]
                gx, gy = xr - xl, yd - yu
                g = abs(gx) + abs(gy)
            else:
                g = 0
            # ±1 step of deterministic jitter breaks up identical-character
            # runs (ordered dithering) — flat `$` fields read as blocks.
            # Edge-aware: skip jitter on strong contours so they render as
            # clean continuous strokes instead of dithered noise.
            if jitter and not (edge_dither and g >= edge_dither):
                j = ((x * 73856093) ^ (y * 19349663) ^ (7 * 83492791)) % 3 - 1
            else:
                j = 0
            ch = ramp[min(n - 1, max(0, idx + j))]
            cls = "dim" if v < BAND_DIM else "lo" if v < BAND_LO else ""
            if (x, y) in lavender:
                cls = "hi"
            elif edges and g >= edges:
                # hybrid edge mapping: on strong contours replace the tone
                # glyph with a stroke perpendicular to the gradient (the
                # stroke keeps the cell's tone class, so edges never glow)
                if abs(gx) >= 2.4 * abs(gy):
                    ch = "|"          # horizontal gradient -> vertical stroke
                elif abs(gy) >= 2.4 * abs(gx):
                    ch = "-"          # vertical gradient -> horizontal stroke
                elif gx * gy > 0:
                    ch = "/"
                else:
                    ch = "\\"
            if cls != "hi" and BAND_DIM <= v < BAND_HI and green_cell(x, y, green_permille):
                cls = "ph"
            row.append((ch, cls))
        grid.append(row)

    if despeckle:
        for _ in range(max(1, despeckle_passes)):
            grid = despeckle_grid(grid)
    if clean_border_on:
        grid = clean_border(grid)
    return grid


def despeckle_grid(grid: list[list[tuple[str, str]]]) -> list[list[tuple[str, str]]]:
    """Blank faint cells with at most one inked 8-neighbour.

    Single characters floating in the negative space are threshold residue,
    not image — removing them keeps the background black so the face owns
    the frame. Strand texture lives in pairs and small groups, which this
    deliberately preserves: cutting those is what fragments the hair.
    Dense regions (the face) are untouched by construction.
    """
    rows, cols = len(grid), len(grid[0])

    def ink(x: int, y: int) -> bool:
        return grid[y][x][0] != " "

    out: list[list[tuple[str, str]]] = []
    for y in range(rows):
        row = []
        for x in range(cols):
            ch, cls = grid[y][x]
            if ch != " " and cls in ("dim", "lo"):
                neighbours = sum(
                    ink(nx, ny)
                    for ny in (y - 1, y, y + 1) for nx in (x - 1, x, x + 1)
                    if (nx, ny) != (x, y) and 0 <= nx < cols and 0 <= ny < rows
                )
                if neighbours <= 1:
                    row.append((" ", ""))
                    continue
            row.append((ch, cls))
        out.append(row)
    return out


def write_txt(grid: list[list[tuple[str, str]]], out: Path) -> None:
    text = "\n".join("".join(c for c, _ in row).rstrip() for row in grid)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")


def write_html(grid: list[list[tuple[str, str]]], out: Path, css_class: str) -> None:
    """Span-annotated Jinja fragment; runs of equal class share one span.

    The glyph ramp includes `{`/`%`/`{#`-adjacent characters, so the body is
    wrapped in {% raw %} — Jinja parses included partials as templates and
    an unguarded `{{` in the art is a fatal syntax error.
    """
    parts = [f'<pre class="{css_class}" aria-hidden="true">{{% raw %}}']
    for row in grid:
        run_cls = ""
        run_text = ""

        def flush() -> None:
            esc = html.escape(run_text, quote=False)
            if run_cls:
                parts.append(f'<span class="aa-{run_cls}">{esc}</span>')
            else:
                parts.append(esc)

        for ch, cls in row:
            if cls != run_cls:
                if run_text:
                    flush()
                run_cls = cls
                run_text = ""
            run_text += ch
        if run_text:
            flush()
        parts.append("\n")
    parts.append('{% endraw %}</pre>')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(parts), encoding="utf-8")


def write_preview(grid: list[list[tuple[str, str]]], out: Path, font_px: float) -> None:
    rows = "".join(
        "".join(f'<span class="aa-{c}">{html.escape(ch, quote=False)}</span>' if c else html.escape(ch, quote=False)
                for ch, c in row)
        + "\n"
        for row in grid
    )
    css = (
        "body{background:#101014;margin:2rem;display:grid;place-items:center}"
        f"pre{{margin:0;font:{font_px}px/1 'JetBrains Mono',ui-monospace,Menlo,monospace;"
        "letter-spacing:0;color:#E6E1D6}"
        ".aa-hi{color:#B4A3E6}.aa-lo{color:#92909A}.aa-dim{color:#65616C}.aa-ph{color:#A3BE8C}"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"<!doctype html><meta charset='utf-8'><style>{css}</style><pre>{rows}</pre>",
                   encoding="utf-8")


def compose(name: str, args, cols: int, crop: tuple[float, float, float, float],
            out_txt: Path, out_html: Path, preview: Path | None, target_w: int):
    # preview font derived so the rendered width matches the site's CSS cap
    # (glyph box 0.6em wide): same on-page footprint at any grid resolution
    font_px = round(target_w / (0.6 * cols), 2)
    img = prepare(crop, cols, args.blur, args.black, args.white,
                  args.contrast, args.pivot, args.sharpen, args.prelocal)
    grid = grid_from(img, cols, args.gamma, args.floor, args.hi_pct,
                     args.steps, args.green, not args.no_despeckle,
                     args.despeckle_passes, args.jitter,
                     args.edge_dither, args.edges, args.clean_border)
    write_txt(grid, out_txt)
    write_html(grid, out_html, args.css_class if name == "desktop" else f"{args.css_class} {args.css_class}-mobile")
    if preview:
        write_preview(grid, preview, font_px)

    cells = sum(len(r) for r in grid)
    ink = sum(1 for r in grid for c, _ in r if c != " ")
    classes = {k: sum(1 for r in grid for _, c in r if c == k)
               for k in ("hi", "lo", "dim", "ph")}
    pct = lambda k: 100.0 * classes[k] / cells
    print(f"{name}: {len(grid)} rows x {cols} cols -> {out_txt.name}, {out_html.name}")
    print(f"  ink {100.0 * ink / cells:.1f}% | lavender {pct('hi'):.1f}% "
          f"| phosphor {pct('ph'):.2f}% | dim {pct('dim'):.1f}%")
    return grid


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cols", type=int, default=72, help="desktop character columns")
    ap.add_argument("--mobile-cols", type=int, default=56, help="mobile character columns")
    ap.add_argument("--crop", type=parse_crop, default=(0.0, 0.0, 1.0, 0.90),
                    help="desktop crop x0,y0,x1,y1 (fractions of the source)")
    ap.add_argument("--mobile-crop", type=parse_crop, default=(0.37, 0.22, 1.0, 0.61),
                    help="mobile crop centered on the eye and scars")
    ap.add_argument("--blur", type=float, default=0.34,
                    help="pre-resize gaussian radius scale (x width/cols); 0 disables. "
                         "0.34 ≈ half the source's 6-7px ink-hatch period, so the hatch "
                         "averages away inside a cell instead of surviving as glyph noise")
    ap.add_argument("--sharpen", type=int, default=80,
                    help="grid-resolution unsharp percent; 0 disables")
    ap.add_argument("--gamma", type=float, default=1.35,
                    help="tone curve exponent; >1 pushes bright skin down the ramp so "
                         "feature lines read as glyph contrast instead of a flat wall")
    ap.add_argument("--contrast", type=float, default=1.2)
    ap.add_argument("--pivot", type=float, default=0.6,
                    help="contrast pivot as fraction of range (skin shading sits near 0.6)")
    ap.add_argument("--black", type=float, default=0.0, help="level-stretch black point (0-1)")
    ap.add_argument("--white", type=float, default=1.0, help="level-stretch white point (0-1)")
    ap.add_argument("--floor", type=float, default=0.20,
                    help="tones below this become blank space; 0.20 keeps dark regions "
                         "coherent instead of fragmenting into faint residue glyphs")
    ap.add_argument("--hi-pct", type=float, default=2.0,
                    help="percent of inked cells coloured lavender (top-K by tone)")
    ap.add_argument("--steps", type=int, default=20,
                    help="tonal steps in the ramp (subsampled); at 8.5px glyphs, steps "
                         "this far apart stay visually distinct — 24+ reads as mush")
    ap.add_argument("--green", type=int, default=5, help="permille of mid-tone cells tinted phosphor")
    ap.add_argument("--no-despeckle", action="store_true",
                    help="keep isolated faint cells (background residue)")
    ap.add_argument("--despeckle-passes", type=int, default=3,
                    help="repeat the despeckle pass; 2-3 also catch strays left "
                         "isolated by an earlier pass")
    ap.add_argument("--jitter", action="store_true",
                    help="enable the ±1 ramp-step dither (off by default: on this source "
                         "it compounds the surviving hatch texture into speckle)")
    ap.add_argument("--prelocal", type=int, default=70,
                    help="pre-downsample local-contrast unsharp percent (adaptive "
                         "local contrast); 0 disables")
    ap.add_argument("--edge-dither", type=int, default=0,
                    help="suppress jitter where the grid gradient exceeds this; 0 disables")
    ap.add_argument("--edges", type=int, default=0,
                    help="replace tone glyphs with orientation strokes where the "
                         "grid gradient exceeds this; 0 disables")
    ap.add_argument("--no-clean-border", dest="clean_border", action="store_false",
                    help="keep faint cells connected to the frame edge "
                         "(background residue floating off the silhouette)")
    ap.add_argument("--css-class", default="ascii-art", help="class for the desktop fragment")
    ap.add_argument("--preview-dir", type=Path, default=None,
                    help="write desktop/mobile standalone HTML previews here")
    ap.add_argument("--out-txt", type=Path, default=ROOT / "static/assets/art/shanks.txt")
    ap.add_argument("--out-html", type=Path, default=ROOT / "templates/partials/shanks-ascii.html")
    ap.add_argument("--mobile-out-txt", type=Path, default=ROOT / "static/assets/art/shanks-mobile.txt")
    ap.add_argument("--mobile-out-html", type=Path,
                    default=ROOT / "templates/partials/shanks-ascii-mobile.html")
    args = ap.parse_args()

    pv_desktop = pv_mobile = None
    if args.preview_dir:
        pv_desktop = args.preview_dir / "desktop.html"
        pv_mobile = args.preview_dir / "mobile.html"

    compose("desktop", args, args.cols, args.crop, args.out_txt, args.out_html,
            pv_desktop, target_w=370)
    compose("mobile", args, args.mobile_cols, args.mobile_crop,
            args.mobile_out_txt, args.mobile_out_html, pv_mobile, target_w=317)


if __name__ == "__main__":
    main()
