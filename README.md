# prλtam — pritamravi.com

A personal digital archive: minimal retro-cyberpunk, 80% editorial restraint,
20% terminal atmosphere. Built with a custom Python static-site generator —
no frameworks, no database, static-first.

```
Understand the fundamentals. Build from scratch. Explore beyond the abstractions.
```

## quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build.py            # → output/
.venv/bin/python build.py --serve    # dev server with live rebuild (127.0.0.1:8000)
```

The `.github/workflows/deploy.yml` workflow can publish to GitHub Pages only
when manually dispatched; pushes to `main` do not publish a website. Production
hosting is separate and uses the Hermes VPS flow below.

## where things live

| Path | What it is |
|---|---|
| `data/site.yaml` | identity, tagline, socials, homepage copy, **currently** list, Spotify config — edit this first |
| `content/pages/` | standalone pages (`about.md`); frontmatter picks the template |
| `content/projects/*.md` | one page per project; `priority` orders lists, `featured: true` puts it on the homepage |
| `content/writing/*.md` | posts — `title/date/category/tags/summary` frontmatter; `draft: true` hides unless `--drafts` |
| `templates/` | Jinja2 templates (`base.html` + pages + partials) |
| `static/` | css, js, robots.txt — copied verbatim |
| `assets/` | web fonts, ASCII art and images; build inputs and unused variants are omitted from `output/` |
| `tools/` | generators: fonts, ASCII art, OG image, Spotify auth helper |
| `worker/` | Cloudflare Worker for Spotify now-playing |
| `lib/` | generator internals (frontmatter, markdown, pygments style) |

## writing a post

Create `content/writing/my-note.md`:

```markdown
---
title: My note
date: 2026-11-02
category: systems
tags: [gpu, inference]
summary: One-sentence hook used on lists, RSS and social cards.
---

Body markdown. `##` headings build the INDEX.TXT sidebar and get
terminal-style `//` prefixes. Fenced code gets Pygments in the site palette.
```

The archive at `/writing/` groups by year; the homepage shows the three
latest; `/feed.xml` and `/sitemap.xml` regenerate on every build.

## artwork

- **Hero**: genuine character-based ASCII, generated from
  `assets/images/original shanks.jpg` (the clean master; the site's hero is
  the text rendering, not a raster):

  ```bash
  uv run tools/generate_shanks_ascii.py
  ```

  One run writes both compositions — a desktop portrait
  (`assets/art/shanks.txt` + `templates/partials/shanks-ascii.html`) and a
  recomposed, face-forward mobile crop (`assets/art/shanks-mobile.txt` +
  `templates/partials/shanks-ascii-mobile.html`). The homepage swaps between
  them at 900px; the mobile art is a separate crop, not a squeeze.
  Deterministic — same input, same output. Colour is generated, not random:
  lavender lands on the top-K brightest inked cells (the eye glint, the
  sword guard), phosphor is a rare midtone scatter. Tune with
  `--preview-dir <dir>` while adjusting `--crop`, `--cols`, `--blur`
  (pre-downsample hatch suppression), `--gamma`, `--contrast`, `--floor`,
  `--prelocal` (pre-downsample local contrast), `--hi-pct` (lavender share)
  and `--green`.
  `tools/ascii_art.py` remains the general-purpose image→ASCII converter.
- **Social preview**: `tools/og_image.py` regenerates
  `assets/branding/og-image.png` (1200×630), served at
  `/assets/branding/og-image.png`.
- **Fonts**: `tools/fonts.py` re-subsets `assets/fonts/*.ttf` to woff2
  (Latin + Greek λ + terminal glyphs for JetBrains Mono).

## spotify now-playing

1. Create an app at <https://developer.spotify.com/dashboard>, register the
   exact redirect URI `http://127.0.0.1:8765/callback`, and allow
   the `user-read-currently-playing` and `user-read-recently-played`
   scopes (the second powers the "played Xm ago" fallback).
2. `.venv/bin/python tools/spotify_auth.py` → prints a refresh token.
   Re-run it if your token predates the recently-played scope.
3. From `worker/`, set `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and
   `SPOTIFY_REFRESH_TOKEN` with `npx wrangler secret put <NAME>`. Keep
   `ALLOWED_ORIGIN` in `wrangler.toml`'s `[vars]`; it is not a secret. An
   `ACCESS_KEY` embedded in a public site's URL is visible to visitors, so
   leave it unset for this public read-only widget unless there is a specific
   reason to retain the gate.
4. Put the worker URL in `data/site.yaml → spotify.worker`
   (include `?key=…` if you set `ACCESS_KEY`).

The worker answers with the live track (title link, artists // album,
▓░ progress meter, clock, animated equalizer) or — when nothing is
playing — the last track with "played Xm ago". The last answer is cached
in localStorage, so revisits render it instantly with "spotify // syncing"
until the fresh answer lands. After two consecutive request failures, the
widget shows an unavailable state and retries after two minutes. The site
never depends on Spotify being available.

## deploying to Hermes with Caddy

Build locally, then copy the generated site to the directory served by the
Dockerized Caddy instance on Hermes:

```bash
.venv/bin/python build.py
rsync -av output/ <user>@<hermes>:<caddy-site-root>/
```

Replace the placeholders with the SSH account, hostname, and site root already
configured on Hermes. Caddy's site root and HTTPS configuration live with the
server deployment; this repository does not contain or deploy that setup.
`output/` is generated during the build and is intentionally not tracked.

After copying a build, verify `/`, `/about/`, `/projects/`, `/writing/`,
`/feed.xml`, `/sitemap.xml`, `/404.html`, the font files, and the Spotify
Worker request over HTTPS. The Worker remains hosted on Cloudflare; this site
build does not contain Spotify credentials. GitHub Actions does not deploy to
Hermes. Manually running the retained GitHub Pages workflow still publishes a
separate Pages site.

## performance notes

- Fonts: 8 subsetted woff2 files (~170 KB total), preloaded critical three,
  `font-display: swap`.
- JS: one small vanilla file, deferred; everything works without it
  (responsive navigation links, copy buttons, TOC scrollspy, reading progress, Spotify are
  progressive enhancements).
- No layout-shifting hero: ASCII art is text; the OG image is static.
- `prefers-reduced-motion` disables the glitch, pulse and transitions.
