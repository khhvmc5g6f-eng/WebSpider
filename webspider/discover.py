"""Discover image URLs and internal links from an HTML page."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

_BG_IMAGE_RE = re.compile(r"background-image\s*:\s*url\((['\"]?)(.*?)\1\)", re.IGNORECASE)
IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp|bmp|svg|avif)(\?.*)?$", re.IGNORECASE)


def _largest_from_srcset(srcset: str) -> str | None:
    """srcset is a comma-separated list of 'url widthDescriptor'; pick the widest."""
    best_url, best_w = None, -1
    for part in srcset.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split()
        url = bits[0]
        width = 0
        if len(bits) > 1 and bits[1].endswith("w"):
            try:
                width = int(bits[1][:-1])
            except ValueError:
                width = 0
        if width >= best_w:
            best_w, best_url = width, url
    return best_url


def find_image_urls(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: set[str] = set()

    for img in soup.find_all("img"):
        for attr in ("src", "data-src", "data-original"):
            val = img.get(attr)
            if val:
                urls.add(val)
        srcset = img.get("srcset") or img.get("data-srcset")
        if srcset:
            best = _largest_from_srcset(srcset)
            if best:
                urls.add(best)

    for source in soup.find_all("source"):
        srcset = source.get("srcset")
        if srcset:
            best = _largest_from_srcset(srcset)
            if best:
                urls.add(best)

    for meta in soup.find_all("meta", attrs={"property": "og:image"}):
        content = meta.get("content")
        if content:
            urls.add(content)

    for tag in soup.find_all(style=True):
        m = _BG_IMAGE_RE.search(tag["style"])
        if m:
            urls.add(m.group(2))

    resolved = {urljoin(base_url, u) for u in urls if u and not u.startswith("data:")}
    return sorted(resolved)


def find_internal_links(html: str, base_url: str, same_domain: bool = True) -> list[str]:
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
