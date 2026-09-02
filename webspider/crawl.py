"""Site-wide BFS crawl: follow internal links, collect images from every page."""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from .discover import find_image_urls, find_internal_links
from .download import Downloader
from .fetch import DEFAULT_USER_AGENT, fetch_rendered, fetch_static, looks_js_dependent, polite_sleep
from .robots import crawl_delay_for, is_allowed


def crawl(
    start_url: str,
    downloader: Downloader,
    max_pages: int = 25,
    max_depth: int = 2,
    same_domain: bool = True,
    render: bool = False,
    render_auto: bool = False,
    delay: float = 0.5,
    user_agent: str = DEFAULT_USER_AGENT,
    respect_robots: bool = True,
    scope_selector: str | None = None,
    cookies_file: str | None = None,
    resume: bool = False,
) -> dict:
    fetch = fetch_rendered if render else fetch_static
    visited: set[str] = set()
    state_path = downloader.out_dir / ".crawl_state.json"
    queue: deque[tuple[str, int]] = deque([(start_url, 0)])

    if resume and state_path.exists():
        try:
            prior = json.loads(state_path.read_text())
            # Guard against a stale state file from a DIFFERENT crawl target
            # sharing this --out directory: if start_url doesn't match, this
            # isn't a continuation of the same crawl, so don't inherit its
            # frontier (that would silently discard the new start_url and
            # crawl the old target's leftover queue instead).
            if prior.get("start_url") == start_url:
                visited = set(prior.get("visited", []))
                pending = [(u, d) for u, d in prior.get("queue", []) if d <= max_depth]
                if pending:
                    # Resume the exact frontier where the last run left off,
                    # instead of restarting from start_url (which is already in
                    # `visited` and would otherwise make the crawl stop
                    # immediately).
                    queue = deque(pending)
        except (json.JSONDecodeError, OSError, ValueError):
            pass

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

        site_delay = max(delay, crawl_delay_for(url, user_agent, respect_robots))

        try:
            result = fetch(url, user_agent=user_agent, cookies_file=cookies_file)
            if not render and render_auto and looks_js_dependent(result):
                result = fetch_rendered(url, user_agent=user_agent, cookies_file=cookies_file)
        except Exception:
            continue
        finally:
            polite_sleep(site_delay)

        if result.status != 200 or not result.text:
            continue

        pages_crawled += 1
        image_candidates = find_image_urls(result.text, url, scope_selector=scope_selector)
        all_records.extend(downloader.download_many(url, image_candidates))

        if depth < max_depth:
            for link in find_internal_links(result.text, url, same_domain=same_domain):
                if link not in visited:
                    queue.append((link, depth + 1))

    state_path.write_text(
        json.dumps({"start_url": start_url, "visited": sorted(visited), "queue": list(queue)})
    )

    return {
        "pages_crawled": pages_crawled,
        "skipped_robots": skipped_robots,
        "records": all_records,
    }
