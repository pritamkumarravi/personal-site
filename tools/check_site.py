"""Check links, canonical URLs, and the sitemap in a production build."""

import tomllib
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"


class Page(HTMLParser):
    def __init__(self, file: Path):
        super().__init__()
        self.ids = set()
        self.links = []
        self.canonicals = []
        self.robots = ""
        self.feed(file.read_text(encoding="utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        for attr in ("href", "src"):
            if attrs.get(attr):
                self.links.append(attrs[attr])
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonicals.append(attrs.get("href"))
        if tag == "meta" and attrs.get("name") == "robots":
            self.robots = attrs.get("content", "")


def main():
    origin = yaml.safe_load((ROOT / "data/site.yaml").read_text(encoding="utf-8"))["url"]
    pages = {file: Page(file) for file in OUT.rglob("*.html")}
    errors = []
    expected_sitemap = set()
    for file, page in pages.items():
        path = "/" + file.relative_to(OUT).as_posix()
        url = origin + path.removesuffix("index.html")
        if path == "/404.html":
            if page.canonicals or "noindex" not in page.robots:
                errors.append("404.html must be noindex and have no canonical URL")
        else:
            if page.canonicals != [url]:
                errors.append(f"{path}: expected canonical URL {url}")
            expected_sitemap.add(url)
        for link in page.links:
            target = urlsplit(urljoin(url, link))
            if f"{target.scheme}://{target.netloc}" != origin:
                continue
            linked_file = OUT / unquote(target.path).lstrip("/")
            if linked_file.is_dir():
                linked_file /= "index.html"
            if not linked_file.is_file():
                errors.append(f"{path}: missing target {link}")
            elif target.fragment and linked_file in pages:
                if unquote(target.fragment) not in pages[linked_file].ids:
                    errors.append(f"{path}: missing anchor {link}")

    if OUT / "index.html" not in pages or OUT / "404.html" not in pages:
        errors.append("The build must include index.html and 404.html")
    sitemap = ET.parse(OUT / "sitemap.xml")
    actual_sitemap = {element.text for element in sitemap.findall(".//{*}loc")}
    if actual_sitemap != expected_sitemap:
        errors.append(f"Sitemap differs from indexable pages: {actual_sitemap ^ expected_sitemap}")
    ET.parse(OUT / "feed.xml")
    tomllib.loads((ROOT / "worker/wrangler.toml").read_text(encoding="utf-8"))

    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Checked {len(pages)} pages, their internal links, sitemap, RSS, and Worker config")


if __name__ == "__main__":
    main()
