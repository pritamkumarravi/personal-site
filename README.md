# prλtam — pritamravi.com

Pritam Ravi's personal site for projects and writing about inference engineering,
ML systems, and GPU performance. Python, Jinja, and Markdown generate the static
site. A separate Cloudflare Worker powers the Spotify card.

## Run locally

With Python 3.13 or newer and [uv](https://docs.astral.sh/uv/):

```sh
uv run --locked build.py
uv run --locked tools/check_site.py
uv run --locked build.py --serve
```

The preview runs at <http://127.0.0.1:8000/> and rebuilds when content, templates,
or public files change. Add `--drafts` to preview unpublished posts. The
preview builds in a temporary directory. The production build writes to
`output/`, which is ignored by Git.

## Repository layout

| Path | Contents |
| --- | --- |
| `content/` | Markdown pages, projects, and posts |
| `data/site.yaml` | Site identity, homepage copy, social links, and Spotify endpoint |
| `templates/` | Jinja layouts, article and project pages, and the ASCII hero |
| `static/` | CSS, JavaScript, and public assets copied into the build |
| `build.py`, `lib/` | Build entry point and content rendering |
| `tools/` | Build checks, artwork generators, and Spotify authorization |
| `tools/sources/` | Original artwork and fonts used by the generators |
| `worker/` | Spotify endpoint and its Wrangler configuration |

## Edit content and artwork

Add posts to `content/writing/` with `title`, `date`, `category`, `tags`, and
`summary` frontmatter. Use `draft: true` to keep a post out of the public build.
The writing archive, RSS feed, and sitemap are generated during the build.

Add projects to `content/projects/`. Use `priority` to order them and
`featured: true` to include them on the homepage. Set `repo` to a public
source URL to show a link on the project detail page.

Regenerate the public artwork and fonts when their inputs change:

```sh
uv run --locked tools/generate_shanks_ascii.py
uv run --locked tools/og_image.py
uv run --locked tools/fonts.py
```

The first command regenerates both ASCII compositions and their HTML
fragments. It accepts `--preview-dir` for standalone previews.

## Cloudflare Pages

Production is at <https://pritamravi.com/>. The Pages project also serves
<https://personal-site-33l.pages.dev/>. Build from the repository root with
Python 3.13 or newer and publish the generated `output` directory. A build
command that works independently of automatic dependency installation is:

```sh
python -m pip install -r requirements.txt && python build.py
```

GitHub Actions builds and checks the site. Manage production deployments in
Cloudflare Pages. When runtime dependencies change, regenerate the Pages
requirements from the lockfile:

```sh
uv export --locked --no-dev --no-emit-project --no-hashes --output-file requirements.txt
```

## Spotify Worker

1. In the [Spotify developer dashboard](https://developer.spotify.com/dashboard),
   register `http://127.0.0.1:8765/callback`. The authorization helper requests
   the currently playing and recently played scopes.
2. Run `uv run --locked tools/spotify_auth.py` to obtain a refresh token.
3. From `worker/`, set `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and
   `SPOTIFY_REFRESH_TOKEN` using `npx wrangler secret put <NAME>`.
4. Review the allowed browser origins in `worker/wrangler.toml`, then run
   `npx wrangler deploy` from `worker/`. Set the resulting `/now` URL in
   `data/site.yaml`. Set `spotify.enabled: false` to hide the card.

The site can use the public read-only endpoint. Use the optional `ACCESS_KEY`
only for private consumers that can keep it out of public URLs. The browser
reuses the last known track and polls while the card is in view.
