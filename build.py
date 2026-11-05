#!/usr/bin/env python3
"""Static site generator for pritamravi.com.

    uv run build.py            # build to output/
    uv run build.py --serve    # build + dev server with live rebuild
    uv run build.py --drafts   # include draft posts
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
from datetime import date, datetime, time as datetime_time, timezone
from html import unescape
from pathlib import Path
from tempfile import TemporaryDirectory

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
    def __init__(self, include_drafts: bool = False, out: Path = OUT) -> None:
        self.include_drafts = include_drafts
        self.out = out
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
        self.site: dict = {}
        self.posts: list[Post] = []
        self.projects: list[Project] = []
        self.pages: dict[str, tuple[str, dict[str, object]]] = {}

    # -- loading ---------------------------------------------------------------

    def load_content(self) -> None:
        self.site = yaml.safe_load((ROOT / "data" / "site.yaml").read_text(encoding="utf-8"))
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
            meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
            html, _ = render_markdown(body)
            self.pages[meta["url"]] = (meta.get("template", "page.html"), {"meta": meta, "body": html})

    # -- rendering ---------------------------------------------------------------

    def render(self, template_name: str, out_path: Path, **ctx) -> None:
        template = self.env.get_template(template_name)
        page = ctx.pop("page", {})
        page["path"] = path_for(out_path.relative_to(self.out))
        page.setdefault("robots", ctx.pop("robots", "index, follow"))
        html = template.render(
            site=self.site,
            nav=NAV,
            page=page,
            now=date.today(),
            **ctx,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")

    def build(self) -> None:
        if self.out.exists():
            shutil.rmtree(self.out)
        shutil.copytree(ROOT / "static", self.out)

        featured = [p for p in self.projects if p.meta.get("featured")]
        by_year: dict[int, list[Post]] = {}
        for p in self.posts:
            by_year.setdefault(p.year, []).append(p)
        # homepage
        self.render("index.html", self.out / "index.html",
                    page=page("home", "home"),
                    featured=featured, recent=self.posts[:3])

        # plain pages (about)
        for url, (template, extra) in self.pages.items():
            self.render(template, self.out / url.lstrip("/") / "index.html",
                        page=page(meta_id(url), extra["meta"].get("title", ""),
                                  description=extra["meta"].get("description")),
                        body=extra["body"], meta=extra["meta"],
                        has_code='class="codehilite"' in extra["body"])

        # projects
        self.render("projects.html", self.out / "projects" / "index.html",
                    page=page("projects", "Projects",
                              description="Engineering experiments in inference, ML systems, GPU performance and creative tooling — built to understand the internals."),
                    all_projects=self.projects)
        for i, proj in enumerate(self.projects):
            prev = self.projects[i - 1] if i > 0 else None
            nxt = self.projects[i + 1] if i + 1 < len(self.projects) else None
            self.render("project.html", self.out / "projects" / proj.slug / "index.html",
                        page=page("project", proj.title, description=proj.tagline),
                        project=proj, prev=prev, next=nxt,
                        has_code='class="codehilite"' in proj.html)

        # writing
        self.render("writing.html", self.out / "writing" / "index.html",
                    page=page("writing", "Writing",
                              description="Technical notes on inference engines, GPU performance, ML systems and building things from scratch."),
                    by_year=sorted(by_year.items(), reverse=True))
        for i, post in enumerate(self.posts):
            prev = self.posts[i - 1] if i > 0 else None
            nxt = self.posts[i + 1] if i + 1 < len(self.posts) else None
            self.render("article.html", self.out / "writing" / post.slug / "index.html",
                        page=page("article", post.title, description=post.summary),
                        post=post, prev=prev, next=nxt,
                        has_code='class="codehilite"' in post.html)

        # 404 + feeds
        self.render("404.html", self.out / "404.html", page=page("404", "404",
                    description="Page not found."), robots="noindex")
        (self.out / "feed.xml").write_text(self.env.get_template("feed.xml").render(
            site=self.site, posts=self.posts, now=date.today()), encoding="utf-8")
        (self.out / "sitemap.xml").write_text(self.env.get_template("sitemap.xml").render(
            site=self.site, posts=self.posts, projects=self.projects,
            pages=dict.fromkeys([*self.pages, "/projects/", "/writing/"])),
            encoding="utf-8")
        (self.out / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\n\nSitemap: {self.site['url']}/sitemap.xml\n",
            encoding="utf-8")

        write_pygments_css(self.out)
        print(f"built {sum(1 for _ in self.out.rglob('*.html'))} pages -> {self.out}")


# -- helpers -------------------------------------------------------------------


def page(id_: str, title: str, description: str | None = None) -> dict:
    return {"id": id_, "title": title, "description": description}


def meta_id(url: str) -> str:
    return url.strip("/").split("/")[-1]


def path_for(path: Path) -> str:
    if path.name == "index.html":
        return "/" if path.parent == Path(".") else f"/{path.parent.as_posix()}/"
    return "/" + path.as_posix()


def load_entry(f: Path, cls):
    meta, body = parse_frontmatter(f.read_text(encoding="utf-8"))
    html, toc = render_markdown(body)
    return cls(
        slug=meta.get("slug", f.stem),
        meta=meta,
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
    return unescape(re.sub(r"<[^>]+>", "", m.group(1)))


def rfc822(d: date | None) -> str:
    return email.utils.format_datetime(
        datetime.combine(d, datetime_time(9), timezone.utc)
    ) if d else ""


def write_pygments_css(out: Path) -> None:
    from pygments.formatters import HtmlFormatter

    from lib.pygments_style import SiteStyle

    css = HtmlFormatter(style=SiteStyle).get_style_defs(".codehilite")
    (out / "css" / "pygments.css").write_text(css + "\n", encoding="utf-8")


# -- dev server ------------------------------------------------------------------


class Rebuilder:
    def __init__(self) -> None:
        self.snapshot: dict[Path, int] = {}

    def sources(self):
        for sub in ("content", "data", "templates", "static"):
            root = ROOT / sub
            for p in root.rglob("*"):
                if p.is_file():
                    yield p

    def changed(self) -> bool:
        snapshot = {p: p.stat().st_mtime_ns for p in self.sources()}
        changed = snapshot != self.snapshot
        self.snapshot = snapshot
        return changed


def serve(drafts: bool, port: int) -> None:
    with TemporaryDirectory(prefix="pritamravi-preview-") as directory:
        reb = Rebuilder()
        reb.changed()
        site = Site(drafts, Path(directory) / "output")
        site.load_content()
        site.build()

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site.out))
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
