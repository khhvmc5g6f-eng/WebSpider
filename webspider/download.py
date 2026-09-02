"""Download images with content-hash dedup and a JSONL manifest."""
from __future__ import annotations

import hashlib
import json
import mimetypes
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse

from .fetch import DEFAULT_USER_AGENT, download_bytes, polite_sleep


@dataclass
class DownloadRecord:
    page_url: str
    image_url: str
    local_path: str | None
    sha1: str | None
    bytes: int
    content_type: str
    status: str  # "saved" | "duplicate" | "skipped" | "error"
    detail: str = ""


def _filename_for(image_url: str, content_type: str, sha1: str) -> str:
    name = Path(urlparse(image_url).path).name
    if name and "." in name:
        return name
    ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".bin"
    return f"{sha1}{ext}"


class Downloader:
    def __init__(
        self,
        out_dir: Path,
        user_agent: str = DEFAULT_USER_AGENT,
        delay: float = 0.5,
        min_bytes: int = 256,
    ):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent
        self.delay = delay
        self.min_bytes = min_bytes
        self.seen_hashes: set[str] = set()
        self.manifest_path = self.out_dir / "manifest.jsonl"

    def _log(self, record: DownloadRecord) -> None:
        with self.manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def download_one(self, page_url: str, image_url: str) -> DownloadRecord:
        try:
            status_code, content_type, content = download_bytes(image_url, self.user_agent)
        except Exception as e:
            rec = DownloadRecord(page_url, image_url, None, None, 0, "", "error", str(e))
            self._log(rec)
            return rec

        polite_sleep(self.delay)

        if status_code != 200 or not content_type.startswith("image/") or len(content) < self.min_bytes:
            rec = DownloadRecord(
                page_url, image_url, None, None, len(content), content_type, "skipped",
                f"http={status_code}",
            )
            self._log(rec)
            return rec

        sha1 = hashlib.sha1(content).hexdigest()
        if sha1 in self.seen_hashes:
            rec = DownloadRecord(page_url, image_url, None, sha1, len(content), content_type, "duplicate")
            self._log(rec)
            return rec

        self.seen_hashes.add(sha1)
        filename = _filename_for(image_url, content_type, sha1)
        local_path = self.out_dir / filename
        if local_path.exists():
            local_path = self.out_dir / f"{sha1}_{filename}"
        local_path.write_bytes(content)

        rec = DownloadRecord(page_url, image_url, str(local_path), sha1, len(content), content_type, "saved")
        self._log(rec)
        return rec

    def download_many(self, page_url: str, image_urls: list[str]) -> list[DownloadRecord]:
        return [self.download_one(page_url, u) for u in image_urls]
