#!/usr/bin/env python3
"""Build deterministic Markdown and JSON indexes for Insyn's manual archive."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urldefrag, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://download.insyn.se/Insyn/Bruksanvisning/"
USER_AGENT = "Insyn-manual-index/1.0 (+https://www.insyn.se/)"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


@dataclass(frozen=True)
class Manual:
    path: str
    name: str
    directory: str
    extension: str
    url: str


def canonical_url(url: str) -> str:
    clean, _fragment = urldefrag(url)
    parts = urlsplit(clean)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, "", ""))


def fetch_html(url: str, retries: int = 3) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=30) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt == retries:
                raise RuntimeError(f"Kunde inte läsa {url}: {error}") from error
            time.sleep(attempt * 2)
    raise AssertionError("unreachable")


def crawl(base_url: str) -> list[Manual]:
    base_url = canonical_url(base_url)
    if not base_url.endswith("/"):
        base_url += "/"

    base = urlsplit(base_url)
    pending = [base_url]
    visited: set[str] = set()
    files: dict[str, Manual] = {}

    while pending:
        directory_url = pending.pop()
        if directory_url in visited:
            continue
        visited.add(directory_url)
        print(f"Skannar {directory_url}", file=sys.stderr)

        parser = LinkParser()
        parser.feed(fetch_html(directory_url))

        for href in parser.links:
            candidate = canonical_url(urljoin(directory_url, href))
            parts = urlsplit(candidate)

            if parts.scheme not in {"http", "https"}:
                continue
            if parts.netloc != base.netloc or not parts.path.startswith(base.path):
                continue
            if candidate == base_url:
                continue

            if parts.path.endswith("/"):
                if candidate not in visited:
                    pending.append(candidate)
                continue

            relative_encoded = parts.path[len(base.path) :]
            if not relative_encoded:
                continue
            relative = unquote(relative_encoded)
            path = PurePosixPath(relative)
            files[candidate] = Manual(
                path=path.as_posix(),
                name=path.name,
                directory="/" if str(path.parent) == "." else path.parent.as_posix(),
                extension=path.suffix.lower().lstrip("."),
                url=candidate,
            )

    return sorted(files.values(), key=lambda item: (item.path.casefold(), item.path))


def markdown_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def render_markdown(base_url: str, manuals: list[Manual]) -> str:
    lines = [
        "# Manualindex",
        "",
        f"Automatiskt index över [{base_url}]({base_url}).",
        "",
        f"Antal filer: **{len(manuals)}**",
        "",
    ]

    current_directory: str | None = None
    for manual in manuals:
        if manual.directory != current_directory:
            current_directory = manual.directory
            lines.extend((f"## {markdown_escape(current_directory)}", ""))
        lines.append(f"- [{markdown_escape(manual.name)}]({manual.url})")

    if not manuals:
        lines.append("Inga filer hittades.")
    lines.append("")
    return "\n".join(lines)


def render_json(base_url: str, manuals: list[Manual]) -> str:
    data = {
        "base_url": base_url,
        "count": len(manuals),
        "files": [
            {
                "path": manual.path,
                "name": manual.name,
                "directory": manual.directory,
                "extension": manual.extension,
                "url": manual.url,
            }
            for manual in manuals
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--markdown", type=Path, default=Path("manual-index.md"))
    parser.add_argument("--json", dest="json_path", type=Path, default=Path("manual-index.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url if args.base_url.endswith("/") else args.base_url + "/"
    manuals = crawl(base_url)
    markdown_changed = write_if_changed(args.markdown, render_markdown(base_url, manuals))
    json_changed = write_if_changed(args.json_path, render_json(base_url, manuals))
    state = "uppdaterat" if markdown_changed or json_changed else "oförändrat"
    print(f"Index {state}: {len(manuals)} filer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
