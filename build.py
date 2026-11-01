#!/usr/bin/env python3
"""Static site generator for pritamravi.com.

    .venv/bin/python build.py            # build to output/
    .venv/bin/python build.py --serve    # build + dev server with live rebuild
    .venv/bin/python build.py --drafts   # include draft posts
"""

from __future__ import annotations

import argparse
import email.utils
import functools
import http.server
import re
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from lib.content import Entry, fmt_date, parse_date, parse_frontmatter, reading_time, render_markdown

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"

NAV = [
    ("about", "/about/"),
    ("projects", "/projects/"),
    ("writing", "/writing/"),
]


@dataclass
class Post(Entry):
    @property
    def url(self) -> str:
        return f"/writing/{self.slug}/"

    @property
    def year(self) -> int:
        return self.date.year if self.date else 1970


@dataclass
class Project(Entry):
    @property
    def url(self) -> str:
        return f"/projects/{self.slug}/"


class Site:
    def __init__(self, include_drafts: bool = False) -> None:
        self.include_drafts = include_drafts
        self.env = Environment(
            loader=FileSystemLoader(ROOT / "templates"),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters.update(
            fmt_date=fmt_date,
            rfc822=rfc822,
        )
        self.site = yaml.safe_load((ROOT / "data" / "site.yaml").read_text())
        self.posts: list[Post] = []
        self.projects: list[Project] = []
        self.pages: dict[str, tuple[str, dict[str, object]]] = {}

    # -- loading ---------------------------------------------------------------

    def load_content(self) -> None:
        # re-read site.yaml here (not just __init__) so the dev server's
        # live rebuild picks up copy/config edits too
        self.site = yaml.safe_load((ROOT / "data" / "site.yaml").read_text())
        self.posts.clear()
        self.projects.clear()
        self.pages.clear()
        for f in sorted((ROOT / "content" / "writing").glob("*.md")):
            post = load_entry(f, Post)
            if post.meta.get("draft") and not self.include_drafts:
                continue
            self.posts.append(post)
        self.posts.sort(key=lambda p: p.date or date.min, reverse=True)

        for f in sorted((ROOT / "content" / "projects").glob("*.md")):
            self.projects.append(load_entry(f, Project))
        self.projects.sort(
            key=lambda p: (int(p.meta.get("priority", 99)), p.slug)
        )

        for f in sorted((ROOT / "content" / "pages").glob("*.md")):
            meta, body = parse_frontmatter(f.read_text())
            html, _ = render_markdown(body)
            self.pages[meta["url"]] = (meta.get("template", "page.html"), {"meta": meta, "body": html})

    # -- rendering ---------------------------------------------------------------

    def render(self, template_name: str, out_path: Path, **ctx) -> None:
        template = self.env.get_template(template_name)
        page = ctx.pop("page", {})
        page.setdefault("path", path_for(out_path))
        page.setdefault("robots", ctx.pop("robots", "index, follow"))
        html = template.render(
            site=self.site,
            nav=NAV,
            posts=self.posts,
            projects=self.projects,
            page=page,
            now=date.today(),
            **ctx,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")

    def build(self) -> None:
        if OUT.exists():
            shutil.rmtree(OUT)
        copy_static()

        featured = [p for p in self.projects if p.meta.get("featured")]
        by_year: dict[int, list[Post]] = {}
        for p in self.posts:
            by_year.setdefault(p.year, []).append(p)
        years = sorted(by_year, reverse=True)

        common = dict(years=years)

        # homepage
        self.render("index.html", OUT / "index.html",
                    page=page("home", "home", description=self.site["home_description"]),
                    featured=featured, recent=self.posts[:3], **common)

        # plain pages (about)
        for url, (template, extra) in self.pages.items():
            self.render(template, OUT / url.lstrip("/") / "index.html",
                        page=page(meta_id(url), extra["meta"].get("title", ""),
                                  description=extra["meta"].get("description")),
                        body=extra["body"], meta=extra["meta"], **common)

        # projects
        self.render("projects.html", OUT / "projects" / "index.html",
                    page=page("projects", "Projects",
                              description="Engineering experiments in inference, ML systems, GPU performance and creative tooling — built to understand the internals."),
                    all_projects=self.projects, **common)
        for i, proj in enumerate(self.projects):
            prev = self.projects[i - 1] if i > 0 else None
            nxt = self.projects[i + 1] if i + 1 < len(self.projects) else None
            self.render("project.html", OUT / "projects" / proj.slug / "index.html",
                        page=page("projects", proj.title, f"/projects/{proj.slug}/",
                                  description=proj.tagline),
                        project=proj, prev=prev, next=nxt, **common)

        # writing
        self.render("writing.html", OUT / "writing" / "index.html",
                    page=page("writing", "Writing",
                              description="Technical notes on inference engines, GPU performance, ML systems and building things from scratch."),
                    by_year=years and [(y, by_year[y]) for y in years],
                    **common)
        for i, post in enumerate(self.posts):
            prev = self.posts[i - 1] if i > 0 else None
            nxt = self.posts[i + 1] if i + 1 < len(self.posts) else None
            self.render("article.html", OUT / "writing" / post.slug / "index.html",
                        page=page("writing", post.title, f"/writing/{post.slug}/",
                                  description=post.summary),
                        post=post, prev=prev, next=nxt, **common)

        # 404 + feeds
        self.render("404.html", OUT / "404.html", page=page("404", "404",
                    description="Page not found."), robots="noindex", **common)
        (OUT / "feed.xml").write_text(self.env.get_template("feed.xml").render(
            site=self.site, posts=self.posts, now=date.today()), encoding="utf-8")
        (OUT / "sitemap.xml").write_text(self.env.get_template("sitemap.xml").render(
            site=self.site, posts=self.posts, projects=self.projects,
            pages=[u for u in self.pages], now=date.today()), encoding="utf-8")

        write_pygments_css()
        print(f"built {sum(1 for _ in OUT.rglob('*.html'))} pages -> {OUT}")


# -- helpers -------------------------------------------------------------------


def page(id_: str, title: str, path: str | None = None, description: str | None = None) -> dict:
    return {"id": id_, "title": title, "path": path, "description": description}


def meta_id(url: str) -> str:
    return url.strip("/").split("/")[-1]


def path_for(out_path: Path) -> str:
    rel = out_path.relative_to(OUT).with_suffix("")
    if rel.name == "index":
        rel = rel.parent
    s = "/" + rel.as_posix()
    if s == "/.":
        return "/"
    if rel.name == "404":
        return s
    return s.rstrip("/") + "/"


def load_entry(f: Path, cls):
    meta, body = parse_frontmatter(f.read_text())
    html, toc = render_markdown(body)
    return cls(
        slug=meta.get("slug", f.stem),
        meta=meta,
        body_md=body,
        html=html,
        toc=toc,
        date=parse_date(meta.get("date")),
        read_minutes=reading_time(body),
        summary=(meta.get("summary") or first_paragraph(html)).strip(),
    )


def first_paragraph(html: str) -> str:
    m = re.search(r"<p>(.*?)</p>", html, re.DOTALL)
    if not m:
        return ""
    return re.sub(r"<[^>]+>", "", m.group(1))


def rfc822(d: date | None) -> str:
    return email.utils.format_datetime(
        datetime_from(d or date(1970, 1, 1))
    ) if d else ""


def datetime_from(d: date):
    from datetime import datetime as dt, timezone

    return dt(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc)


def copy_static() -> None:
    shutil.copytree(ROOT / "static", OUT, dirs_exist_ok=True)
    # The hero is genuine ASCII (templates/partials/shanks-ascii*.html), so
    # the raster Shanks sources stay out of the deploy: "original shanks.jpg"
    # is the generator's input, "shanks ascii.png" its 3.6 MB textured master
    # and "shanks ascii-hero.webp" a former raster derivative.
    shutil.copytree(
        ROOT / "assets", OUT / "assets", dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(
            "*.ttf", ".DS_Store",
            "original shanks.jpg", "shanks ascii.png", "shanks ascii-hero.webp",
            "blackhole.jpg", "vagabond peak.jpeg", "favicon-now-package",
        ),
    )


def write_pygments_css() -> None:
    from pygments.formatters import HtmlFormatter

    from lib.pygments_style import SiteStyle

    css = HtmlFormatter(style=SiteStyle).get_style_defs(".codehilite")
    (OUT / "css" / "pygments.css").write_text(css + "\n", encoding="utf-8")


# -- dev server ------------------------------------------------------------------


class Rebuilder:
    def __init__(self, drafts: bool) -> None:
        self.drafts = drafts
        self.stamp = 0.0

    def sources(self):
        for sub in ("content", "data", "templates", "static", "assets", "lib"):
            root = ROOT / sub
            for p in root.rglob("*"):
                if p.is_file():
                    yield p

    def changed(self) -> bool:
        latest = max((p.stat().st_mtime for p in self.sources()), default=0.0)
        if latest > self.stamp:
            self.stamp = latest
            return True
        return False


def serve(drafts: bool, port: int) -> None:
    reb = Rebuilder(drafts)
    reb.changed()
    site = Site(drafts)
    site.load_content()
    site.build()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)

    def watch() -> None:
        while True:
            time.sleep(1.0)
            try:
                if reb.changed():
                    print("·· change detected, rebuilding")
                    site.load_content()
                    site.build()
            except Exception as exc:  # keep the server alive through content typos
                print(f"!! rebuild failed: {exc}", file=sys.stderr)

    threading.Thread(target=watch, daemon=True).start()
    print(f"serving http://127.0.0.1:{port}/  (ctrl-c to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--serve", action="store_true", help="build and run a local dev server")
    ap.add_argument("--drafts", action="store_true", help="include draft posts")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    if args.serve:
        serve(args.drafts, args.port)
        return

    site = Site(args.drafts)
    site.load_content()
    site.build()


if __name__ == "__main__":
    main()
