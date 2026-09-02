"""Page fetching: static (requests) and JS-rendered (Playwright, optional)."""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_USER_AGENT = (
    "WebSpiderBot/0.1 (+https://github.com/khhvmc5g6f-eng/WebSpider; research/personal use)"
)


@dataclass
class FetchResult:
    url: str
    status: int
    content_type: str
    text: str | None
    content: bytes | None


def _session(user_agent: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent})
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def fetch_static(url: str, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 15) -> FetchResult:
    resp = _session(user_agent).get(url, timeout=timeout)
    ctype = resp.headers.get("Content-Type", "")
    is_text = "text" in ctype or "html" in ctype or "json" in ctype
    return FetchResult(
        url=resp.url,
        status=resp.status_code,
        content_type=ctype,
        text=resp.text if is_text else None,
        content=resp.content,
    )


def fetch_rendered(url: str, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 20) -> FetchResult:
    """Render with a plain headless Chromium via Playwright. No fingerprint
    spoofing or anti-bot evasion — only for pages that need JS to populate
    content. Requires `pip install webspider[render]` + `playwright install chromium`.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Rendering requires the optional dependency. Install with: "
            "pip install 'webspider[render]' && playwright install chromium"
        ) from e

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=user_agent)
        response = page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
        html = page.content()
        status = response.status if response else 0
        browser.close()
    return FetchResult(url=url, status=status, content_type="text/html", text=html, content=None)


def download_bytes(url: str, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 15) -> tuple[int, str, bytes]:
    resp = _session(user_agent).get(url, timeout=timeout)
    return resp.status_code, resp.headers.get("Content-Type", ""), resp.content


def polite_sleep(delay: float) -> None:
    if delay > 0:
        time.sleep(delay)
