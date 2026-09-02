from unittest.mock import patch

from webspider.discover import ImageCandidate
from webspider.download import Downloader


def test_concurrent_downloads_of_identical_content_dedupe_correctly(tmp_path):
    """Regression test: without a lock around the check-dedup/write critical
    section, N threads downloading identical content could all pass the
    'not seen yet' check before any of them recorded the hash, saving the
    same content N times instead of once."""
    identical_content = b"x" * 300  # over min_bytes

    def fake_download_bytes(url, user_agent, cookies_file=None):
        return 200, "image/jpeg", identical_content

    downloader = Downloader(tmp_path, concurrency=16, delay=0)
    candidates = [ImageCandidate(url=f"https://example.com/img{i}.jpg") for i in range(16)]

    with patch("webspider.download.download_bytes", side_effect=fake_download_bytes):
        records = downloader.download_many("https://example.com/", candidates)

    saved = [r for r in records if r.status == "saved"]
    duplicates = [r for r in records if r.status == "duplicate"]
    assert len(saved) == 1, f"expected exactly one save, got {len(saved)}"
    assert len(duplicates) == 15
    # Only one file should actually exist on disk for this content.
    saved_files = list(tmp_path.glob("*.jpg"))
    assert len(saved_files) == 1
