"""Discover image URLs (with alt text) and internal links from an HTML page."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

_BG_IMAGE_RE = re.compile(r"background-image\s*:\s*url\((['\"]?)(.*?)\1\)", re.IGNORECASE)


@dataclass(frozen=True)
class ImageCandidate:
    url: str
    alt: str = ""


def _largest_from_srcset(srcset: str) -> str | None:
    """srcset is a comma-separated list of 'url descriptor', where descriptor is
    either a width ('400w') or a pixel density ('2x'); a bare url with no
    descriptor implicitly means 1x. Real markup never mixes 'w' and 'x' in one
    srcset, so comparing raw descriptor values (regardless of which unit) picks
    the largest/densest entry either way. Strict '>' (not '>=') keeps the first
    entry on a tie instead of order-dependently picking the last."""
    best_url, best_key = None, -1.0
    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split()
        url = bits[0]
        key = 1.0  # implicit descriptor per the HTML spec
        if len(bits) > 1 and bits[1][-1:] in ("w", "x"):
            try:
                key = float(bits[1][:-1])
            except ValueError:
                key = 1.0
        if key > best_key:
            best_key, best_url = key, url
    return best_url


def _jsonld_image_urls(soup: BeautifulSoup) -> set[str]:
    """Pull image URLs out of schema.org JSON-LD blocks (ImageObject, or an
    'image' field that's a string, list of strings, or list of ImageObjects)."""
    found: set[str] = set()

    def _collect(value):
        if isinstance(value, str):
            found.add(value)
        elif isinstance(value, dict):
            url = value.get("url") or value.get("contentUrl")
            if url:
                found.add(url)
        elif isinstance(value, list):
            for item in value:
                _collect(item)

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        blocks = data if isinstance(data, list) else [data]
        # Many real-world sites (WordPress/Yoast SEO and others) wrap every node
        # in a top-level "@graph" list rather than exposing "image" directly.
        graph_nodes = []
        for block in blocks:
            if isinstance(block, dict) and isinstance(block.get("@graph"), list):
                graph_nodes.extend(block["@graph"])
        for block in blocks + graph_nodes:
            if not isinstance(block, dict):
                continue
            if "image" in block:
                _collect(block["image"])
            # A graph node can also be the ImageObject itself, standalone,
            # rather than referenced via another node's "image" field.
            if "ImageObject" in str(block.get("@type", "")):
                _collect(block)
    return found


def find_image_urls(html: str, base_url: str, scope_selector: str | None = None) -> list[ImageCandidate]:
    """Find candidate images. If scope_selector is given (a CSS selector), only
    search within matching elements — useful to target e.g. a '.gallery' container
    and ignore site chrome (nav/footer icons, ads)."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    search_roots = soup.select(scope_selector) if scope_selector else [soup]

    candidates: dict[str, str] = {}  # raw_url -> alt text

    for root in search_roots:
        for img in root.find_all("img"):
            alt = img.get("alt", "") or ""
            for attr in ("src", "data-src", "data-original"):
                val = img.get(attr)
                if val:
                    candidates.setdefault(val, alt)
            srcset = img.get("srcset") or img.get("data-srcset")
            if srcset:
                best = _largest_from_srcset(srcset)
                if best:
                    candidates.setdefault(best, alt)

        for source in root.find_all("source"):
            srcset = source.get("srcset")
            if srcset:
                best = _largest_from_srcset(srcset)
                if best:
                    candidates.setdefault(best, "")

        for meta in root.find_all("meta", attrs={"property": "og:image"}):
            content = meta.get("content")
            if content:
                candidates.setdefault(content, "")

        for tag in root.find_all(style=True):
            m = _BG_IMAGE_RE.search(tag["style"])
            if m:
                candidates.setdefault(m.group(2), "")

    if not scope_selector:
        # JSON-LD is document-level metadata; only include it for whole-page scans.
        for url in _jsonld_image_urls(soup):
            candidates.setdefault(url, "")

    out = []
    for raw_url, alt in candidates.items():
        if not raw_url or raw_url.startswith("data:"):
            continue
        resolved = urljoin(base_url, raw_url)
        if urlparse(resolved).scheme not in ("http", "https"):
            continue  # e.g. javascript:, mailto: slipped in via a crafted style/attr
        out.append(ImageCandidate(url=resolved, alt=alt))
    out.sort(key=lambda c: c.url)
    return out


def find_internal_links(html: str, base_url: str, same_domain: bool = True) -> list[str]:
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    base_host = urlparse(base_url).netloc
    links: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].split("#")[0])
        if not href.startswith(("http://", "https://")):
            continue
        if same_domain and urlparse(href).netloc != base_host:
            continue
        links.add(href)
    return sorted(links)
