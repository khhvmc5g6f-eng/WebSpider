"""Page fetching: static (requests) and JS-rendered (Playwright, optional)."""
from __future__ import annotations

import http.cookiejar
import re
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


def _session(user_agent: str, cookies_file: str | None = None) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent})
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    if cookies_file:
        # Netscape-format cookies.txt from the user's own browser session — this
        # lets WebSpider access pages the user is legitimately logged into. It is
        # not a bypass mechanism: it only works for accounts/sessions the user
        # already has, exactly like opening the page in their own browser.
        jar = http.cookiejar.MozillaCookieJar(cookies_file)
        jar.load(ignore_discard=True, ignore_expires=True)
        s.cookies = jar
    return s


def fetch_static(
    url: str,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = 15,
    cookies_file: str | None = None,
) -> FetchResult:
    resp = _session(user_agent, cookies_file).get(url, timeout=timeout)
    ctype = resp.headers.get("Content-Type", "")
    is_text = "text" in ctype or "html" in ctype or "json" in ctype
    return FetchResult(
        url=resp.url,
        status=resp.status_code,
        content_type=ctype,
        text=resp.text if is_text else None,
        content=resp.content,
    )


def fetch_rendered(
    url: str,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = 20,
    cookies_file: str | None = None,
) -> FetchResult:
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
        context = browser.new_context(user_agent=user_agent)
        if cookies_file:
            jar = http.cookiejar.MozillaCookieJar(cookies_file)
            jar.load(ignore_discard=True, ignore_expires=True)
            context.add_cookies(
                [
                    {
                        "name": c.name,
                        "value": c.value,
                        "domain": c.domain,
                        "path": c.path or "/",
                    }
                    for c in jar
                ]
            )
        page = context.new_page()
        response = page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
        html = page.content()
        status = response.status if response else 0
        browser.close()
    return FetchResult(url=url, status=status, content_type="text/html", text=html, content=None)


def looks_js_dependent(result: FetchResult) -> bool:
    """Heuristic for 'this static fetch probably missed the real content':
    very little visible text plus a common SPA root div with nothing inside it,
    or a <noscript> warning. Used by --render auto to decide whether to retry
    with headless rendering instead of guessing up front."""
    if not result.text:
        return False
    text = result.text
    lower = text.lower()
    visible_len = len(re.sub(r"<[^>]+>", "", text).strip())
    spa_roots = ('id="root"', "id='root'", 'id="app"', "id='app'", "id=\"__next\"")
    has_empty_spa_root = any(root in lower for root in spa_roots) and visible_len < 500
    has_noscript_warning = "<noscript>" in lower and "enable javascript" in lower
    return has_empty_spa_root or has_noscript_warning or visible_len < 200


def download_bytes(
    url: str,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = 15,
    cookies_file: str | None = None,
) -> tuple[int, str, bytes]:
    resp = _session(user_agent, cookies_file).get(url, timeout=timeout)
    return resp.status_code, resp.headers.get("Content-Type", ""), resp.content


def polite_sleep(delay: float) -> None:
    if delay > 0:
        time.sleep(delay)
