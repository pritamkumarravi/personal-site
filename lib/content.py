"""Content loading: frontmatter parsing, Markdown rendering, models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import markdown as md_lib
import yaml

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a `---`-delimited YAML frontmatter block from the body."""
    m = FM_RE.match(text)
    if not m:
        return {}, text
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError("frontmatter must be a YAML mapping")
    return meta, text[m.end():]


def reading_time(text: str) -> int:
    words = len(re.sub(r"\s+", " ", text).split())
    return max(1, round(words / 220))


def render_markdown(text: str) -> tuple[str, str]:
    """Return (html, toc_html) for a Markdown body."""
    from markdown.extensions.codehilite import CodeHiliteExtension
    from markdown.extensions.toc import TocExtension

    md = md_lib.Markdown(
        extensions=[
            "extra",
            "sane_lists",
            TocExtension(slugify=_slugify, permalink=False),
            CodeHiliteExtension(guess_lang=False, css_class="codehilite"),
        ],
        output_format="html5",
    )
    html = md.convert(text)
    return html, md.toc if md.toc_tokens else ""


def _slugify(value, separator="-"):
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[{}\s]+".format(re.escape(separator)), separator, value).replace(" ", separator)


@dataclass
class Entry:
    """A dated content entry (writing post or project page)."""

    slug: str
    meta: dict
    html: str = ""
    toc: str = ""
    date: date | None = None
    read_minutes: int = 1
    summary: str = ""

    def __getattr__(self, key):  # convenience: entry.title -> entry.meta["title"]
        try:
            return self.meta[key]
        except KeyError:
            raise AttributeError(key)

    @property
    def url(self) -> str:
        raise NotImplementedError


def parse_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value.strip())
    return None


def fmt_date(d: date | None) -> str:
    """Archive-style stamp: 2026.01.15"""
    return d.strftime("%Y.%m.%d") if d else ""
