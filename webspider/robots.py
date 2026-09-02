"""robots.txt compliance (disallow rules + Crawl-delay), cached per domain."""
from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

_cache: dict[str, RobotFileParser] = {}


def _parser_for(url: str) -> RobotFileParser:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _cache:
        rp = RobotFileParser()
        rp.set_url(f"{origin}/robots.txt")
        try:
            rp.read()
        except Exception:
            # No robots.txt or unreachable: treat as allow-all, no extra delay.
            rp.parse([])
        _cache[origin] = rp
    return _cache[origin]


def is_allowed(url: str, user_agent: str, respect: bool = True) -> bool:
    if not respect:
        return True
    try:
        return _parser_for(url).can_fetch(user_agent, url)
    except Exception:
        return True


def crawl_delay_for(url: str, user_agent: str, respect: bool = True) -> float:
    """Return the site's requested Crawl-delay in seconds, or 0.0 if none/disabled."""
    if not respect:
        return 0.0
    try:
        delay = _parser_for(url).crawl_delay(user_agent)
        return float(delay) if delay else 0.0
    except Exception:
        return 0.0
