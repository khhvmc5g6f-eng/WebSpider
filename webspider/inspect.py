"""Find data present in a page's own code/network traffic that never makes it
into the rendered DOM: embedded framework hydration state (Next.js
__NEXT_DATA__, and a best-effort scan for Nuxt/generic window.__X__ blobs),
and — optionally, via headless-browser network capture — the JSON API
responses the page's own JavaScript loads when it renders normally.

This reads what a real browsing session of the page already loads when
opened normally; it does not probe for undocumented endpoints or fuzz for
hidden functionality. Useful for research/content-mining where the rendered
HTML is a subset of what the page's own code actually has (extra images,
extra fields, source links that aren't rendered as clickable <a> tags)."""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

_IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp|bmp|avif)(\?.*)?$", re.IGNORECASE)


def _find_balanced_json(text: str, start: int) -> str | None:
    """text[start] must be '{' or '['. Returns the balanced substring, respecting
    quoted strings (so a brace inside a string literal doesn't throw off depth)."""
    open_ch = text[start]
    close_ch = {"{": "}", "[": "]"}.get(open_ch)
    if close_ch is None:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def extract_embedded_state(html: str) -> dict:
    """Best-effort extraction of common SSR-framework hydration state blobs.
    __NEXT_DATA__ is always plain JSON by framework design and parses
    reliably. Nuxt's __NUXT__ and other generic window.__X__ patterns are
    sometimes a JS function call with variable substitution rather than pure
    JSON (older Nuxt) — those are skipped rather than mis-parsed."""
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    found: dict = {}

    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and next_data.string:
        try:
            found["__NEXT_DATA__"] = json.loads(next_data.string)
        except json.JSONDecodeError:
            pass

    for script in soup.find_all("script", attrs={"type": "application/json"}):
        sid = script.get("id")
        if sid and sid != "__NEXT_DATA__" and script.string:
            try:
                found[sid] = json.loads(script.string)
            except json.JSONDecodeError:
                continue

    for match in re.finditer(r"window\.(__[A-Za-z_]+__)\s*=\s*", html):
        var_name = match.group(1)
        if var_name in found:
            continue
        pos = match.end()
        if pos < len(html) and html[pos] in "{[":
            blob = _find_balanced_json(html, pos)
            if blob:
                try:
                    found[var_name] = json.loads(blob)
                except json.JSONDecodeError:
                    continue  # not pure JSON (e.g. an IIFE with variable substitution)

    return found


def find_urls_in_data(data, base_url: str) -> dict:
    """Walk arbitrary nested JSON and pull out string values that look like
    URLs, split into images vs other links, resolved against base_url."""
    images: set[str] = set()
    links: set[str] = set()

    def _walk(value):
        if isinstance(value, str):
            if value.startswith(("http://", "https://", "/")) and len(value) < 2000:
                resolved = urljoin(base_url, value)
                if urlparse(resolved).scheme not in ("http", "https"):
                    return
                (images if _IMAGE_EXT_RE.search(resolved) else links).add(resolved)
        elif isinstance(value, dict):
            for v in value.values():
                _walk(v)
        elif isinstance(value, list):
            for v in value:
                _walk(v)

    _walk(data)
    return {"images": sorted(images), "links": sorted(links)}


def capture_network_json(url: str, user_agent: str | None = None, timeout: int = 20) -> list[dict]:
    """Load the page in a headless browser and record every response with a
    JSON content-type — the API calls the page's own JS makes on a normal
    page load. Requires webspider[render] (Playwright). No stealth/fingerprint
    spoofing — same as fetch.fetch_rendered."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Network capture requires the optional dependency. Install with: "
            "pip install 'webspider[render]' && playwright install chromium"
        ) from e
    from .fetch import DEFAULT_USER_AGENT

    user_agent = user_agent or DEFAULT_USER_AGENT
    captured: list[dict] = []

    def _on_response(response):
        ctype = response.headers.get("content-type", "")
        if "json" not in ctype:
            return
        try:
            body = response.json()
        except Exception:
            return
        captured.append({"url": response.url, "status": response.status, "body": body})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=user_agent)
        page.on("response", _on_response)
        page.goto(url, timeout=timeout * 1000, wait_until="networkidle")
        browser.close()
    return captured


def inspect_page(html: str, url: str, capture_network: bool = False, user_agent: str | None = None) -> dict:
    """Combine embedded-state extraction with (optionally) live network
    capture, surfacing image/link URLs found in that data — the content a
    DOM-only scan (discover.py) misses because it's never rendered as an
    <img>/<a> tag, only consumed by the page's own JavaScript."""
    embedded_state = extract_embedded_state(html)
    all_images: set[str] = set()
    all_links: set[str] = set()

    for blob in embedded_state.values():
        found = find_urls_in_data(blob, url)
        all_images.update(found["images"])
        all_links.update(found["links"])

    network_responses = []
    if capture_network:
        responses = capture_network_json(url, user_agent=user_agent)
        network_responses = [{"url": r["url"], "status": r["status"]} for r in responses]
        for r in responses:
            found = find_urls_in_data(r["body"], url)
            all_images.update(found["images"])
            all_links.update(found["links"])

    return {
        "url": url,
        "embedded_state_keys": list(embedded_state.keys()),
        "embedded_state": embedded_state,
        "network_responses": network_responses,
        "discovered_images": sorted(all_images),
        "discovered_links": sorted(all_links),
    }
