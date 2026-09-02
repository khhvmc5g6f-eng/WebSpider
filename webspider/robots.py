"""robots.txt compliance, cached per domain."""
from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

_cache: dict[str, RobotFileParser] = {}


def _parser_for(url: str, user_agent: str) -> RobotFileParser:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _cache:
        rp = RobotFileParser()
        rp.set_url(f"{origin}/robots.txt")
        try:
            rp.read()
        except Exception:
            # No robots.txt or unreachable: treat as allow-all.
            rp.parse([])
        _cache[origin] = rp
    return _cache[origin]


def is_allowed(url: str, user_agent: str, respect: bool = True) -> bool:
    if not respect:
        return True
    try:
        return _parser_for(url, user_agent).can_fetch(user_agent, url)
    except Exception:
        return True
