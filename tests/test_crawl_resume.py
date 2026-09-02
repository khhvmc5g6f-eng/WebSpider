import json

from webspider.crawl import crawl
from webspider.download import Downloader


class _FakeResult:
    def __init__(self, status, text):
        self.status = status
        self.text = text


def _make_fetch(pages: dict):
    def fetch(url, user_agent=None, cookies_file=None):
        return pages.get(url, _FakeResult(404, None))
    return fetch


def test_resume_ignores_stale_state_from_a_different_start_url(tmp_path, monkeypatch):
    """Regression test: a leftover queue from crawling site A must not hijack
    a later crawl of a different site B pointed at the same --out directory."""
    state_path = tmp_path / ".crawl_state.json"
    state_path.write_text(json.dumps({
        "start_url": "https://site-a.example/",
        "visited": ["https://site-a.example/"],
        "queue": [["https://site-a.example/leftover", 1]],
    }))

    pages = {
        "https://site-b.example/": _FakeResult(200, '<html><body>hello</body></html>'),
    }
    monkeypatch.setattr("webspider.crawl.fetch_static", _make_fetch(pages))
    monkeypatch.setattr("webspider.crawl.is_allowed", lambda *a, **k: True)
    monkeypatch.setattr("webspider.crawl.crawl_delay_for", lambda *a, **k: 0)

    downloader = Downloader(tmp_path, delay=0)
    result = crawl(
        "https://site-b.example/", downloader, max_pages=5, max_depth=1,
        resume=True, respect_robots=False,
    )

    # Must have crawled site B's start_url, not site A's leftover page.
    assert result["pages_crawled"] == 1
    new_state = json.loads(state_path.read_text())
    assert new_state["start_url"] == "https://site-b.example/"
    assert "https://site-a.example/leftover" not in new_state["visited"]
