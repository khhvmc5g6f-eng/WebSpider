"""Fast URL discovery: robots.txt 'Sitemap:' directives + sitemap.xml (incl.
sitemap indexes), falling back to a shallow link crawl. No downloads — this is
reconnaissance to scope a crawl before committing to one."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import deque
from urllib.parse import urlparse

from .discover import find_internal_links
from .fetch import DEFAULT_USER_AGENT, fetch_static
from .robots import is_allowed


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """Returns (page_urls, nested_sitemap_urls)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return [], []

    urls, sitemaps = [], []
    for elem in root:
        if _local_tag(elem.tag) not in ("url", "sitemap"):
            continue
        loc = None
        for child in elem:
            if _local_tag(child.tag) == "loc" and child.text:
                loc = child.text.strip()
                break
        if not loc:
            continue
        (sitemaps if _local_tag(elem.tag) == "sitemap" else urls).append(loc)
    return urls, sitemaps


def discover_sitemap_urls(
    origin: str, user_agent: str = DEFAULT_USER_AGENT, max_urls: int = 5000, respect_robots: bool = True
) -> list[str]:
    robots_result = fetch_static(f"{origin}/robots.txt", user_agent=user_agent)
    sitemap_urls = []
    if robots_result.status == 200 and robots_result.text:
        for line in robots_result.text.splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_urls.append(line.split(":", 1)[1].strip())
    if not sitemap_urls:
        sitemap_urls = [f"{origin}/sitemap.xml"]

    found: list[str] = []
    queue = deque(sitemap_urls)
    seen_sitemaps: set[str] = set()
    while queue and len(found) < max_urls:
        sm_url = queue.popleft()
        if sm_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sm_url)
        if not is_allowed(sm_url, user_agent, respect_robots):
            continue
        try:
            result = fetch_static(sm_url, user_agent=user_agent)
        except Exception:
            continue
        if result.status != 200 or not result.text:
            continue
        page_urls, nested = _parse_sitemap_xml(result.text)
        found.extend(page_urls)
        if len(found) >= max_urls:
            break  # don't hold/parse further sitemap files once we have enough
        queue.extend(u for u in nested if u not in seen_sitemaps)
    return found[:max_urls]


def discover_via_link_crawl(
    start_url: str,
    max_pages: int = 25,
    same_domain: bool = True,
    user_agent: str = DEFAULT_USER_AGENT,
    respect_robots: bool = True,
) -> list[str]:
    visited: set[str] = set()
    queue: deque[str] = deque([start_url])
    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        if not is_allowed(url, user_agent, respect_robots):
            continue
        try:
            result = fetch_static(url, user_agent=user_agent)
        except Exception:
            continue
        if result.status != 200 or not result.text:
            continue
        for link in find_internal_links(result.text, url, same_domain=same_domain):
            if link not in visited:
                queue.append(link)
    return sorted(visited)


def discover_urls(
    start_url: str,
    max_pages: int = 25,
    same_domain: bool = True,
    user_agent: str = DEFAULT_USER_AGENT,
    respect_robots: bool = True,
) -> dict:
    parsed = urlparse(start_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    sitemap_urls = discover_sitemap_urls(origin, user_agent=user_agent, max_urls=max_pages, respect_robots=respect_robots)
    if sitemap_urls:
        return {"source": "sitemap", "urls": sitemap_urls[:max_pages]}
    crawled = discover_via_link_crawl(
        start_url, max_pages=max_pages, same_domain=same_domain, user_agent=user_agent, respect_robots=respect_robots
    )
    return {"source": "link-crawl", "urls": crawled}
