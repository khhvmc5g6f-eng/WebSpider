"""Site-wide BFS crawl: follow internal links, collect images from every page."""
from __future__ import annotations

from collections import deque

from .discover import find_image_urls, find_internal_links
from .download import Downloader
from .fetch import DEFAULT_USER_AGENT, fetch_rendered, fetch_static, polite_sleep
from .robots import is_allowed


def crawl(
    start_url: str,
    downloader: Downloader,
    max_pages: int = 25,
    max_depth: int = 2,
    same_domain: bool = True,
    render: bool = False,
    delay: float = 0.5,
    user_agent: str = DEFAULT_USER_AGENT,
    respect_robots: bool = True,
) -> dict:
    fetch = fetch_rendered if render else fetch_static
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    pages_crawled = 0
    all_records = []
    skipped_robots = []

    while queue and pages_crawled < max_pages:
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if not is_allowed(url, user_agent, respect_robots):
            skipped_robots.append(url)
            continue

        try:
            result = fetch(url, user_agent=user_agent)
        except Exception:
            continue
        finally:
            polite_sleep(delay)

        if result.status != 200 or not result.text:
            continue

        pages_crawled += 1
        image_urls = find_image_urls(result.text, url)
        all_records.extend(downloader.download_many(url, image_urls))

        if depth < max_depth:
            for link in find_internal_links(result.text, url, same_domain=same_domain):
                if link not in visited:
                    queue.append((link, depth + 1))

    return {
        "pages_crawled": pages_crawled,
        "skipped_robots": skipped_robots,
        "records": all_records,
    }
