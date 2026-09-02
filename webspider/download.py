"""Download images concurrently, with content-hash dedup, optional dimension
validation, and a resumable JSONL manifest."""
from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse

from .discover import ImageCandidate
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
    alt: str = ""
    width: int | None = None
    height: int | None = None
    detail: str = ""


def _filename_for(image_url: str, content_type: str, sha1: str) -> str:
    name = Path(urlparse(image_url).path).name
    if name and "." in name:
        return name
    ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".bin"
    return f"{sha1}{ext}"


def _image_dimensions(content: bytes) -> tuple[int, int] | None:
    """Best-effort (width, height) via Pillow. Returns None if Pillow isn't
    installed (optional `pip install webspider[images]`) or the bytes aren't
    a decodable image."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(io.BytesIO(content)) as im:
            return im.size
    except Exception:
        return None


class Downloader:
    def __init__(
        self,
        out_dir: Path,
        user_agent: str = DEFAULT_USER_AGENT,
        delay: float = 0.5,
        min_bytes: int = 256,
        concurrency: int = 1,
        cookies_file: str | None = None,
        min_width: int | None = None,
        min_height: int | None = None,
        resume: bool = False,
    ):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent
        self.delay = delay
        self.min_bytes = min_bytes
        self.concurrency = max(1, concurrency)
        self.cookies_file = cookies_file
        self.min_width = min_width
        self.min_height = min_height
        self.seen_hashes: set[str] = set()
        self.seen_image_urls: set[str] = set()
        self.manifest_path = self.out_dir / "manifest.jsonl"
        # Guards the check-dedup / pick-filename / write-file critical section so
        # concurrent workers (--concurrency > 1) with identical content or
        # colliding filenames can't both pass the check before either writes.
        self._lock = threading.Lock()

        if resume and self.manifest_path.exists():
            for line in self.manifest_path.read_text(encoding="utf-8").splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("sha1"):
                    self.seen_hashes.add(rec["sha1"])
                if rec.get("status") in ("saved", "duplicate", "skipped"):
                    self.seen_image_urls.add(rec["image_url"])

    def _log(self, record: DownloadRecord) -> None:
        with self.manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record)) + "\n")

    def download_one(self, page_url: str, candidate: ImageCandidate) -> DownloadRecord:
        image_url, alt = candidate.url, candidate.alt

        if image_url in self.seen_image_urls:
            rec = DownloadRecord(page_url, image_url, None, None, 0, "", "skipped", alt, detail="resumed")
            return rec  # already logged in a prior run; don't re-log

        try:
            status_code, content_type, content = download_bytes(
                image_url, self.user_agent, cookies_file=self.cookies_file
            )
        except Exception as e:
            rec = DownloadRecord(page_url, image_url, None, None, 0, "", "error", alt, detail=str(e))
            self._log(rec)
            return rec
        finally:
            polite_sleep(self.delay)

        if status_code != 200 or not content_type.startswith("image/") or len(content) < self.min_bytes:
            rec = DownloadRecord(
                page_url, image_url, None, None, len(content), content_type, "skipped", alt,
                detail=f"http={status_code}",
            )
            self._log(rec)
            return rec

        dims = _image_dimensions(content) if (self.min_width or self.min_height) else None
        if dims and (
            (self.min_width and dims[0] < self.min_width) or (self.min_height and dims[1] < self.min_height)
        ):
            rec = DownloadRecord(
                page_url, image_url, None, None, len(content), content_type, "skipped", alt,
                width=dims[0], height=dims[1], detail="below min dimensions",
            )
            self._log(rec)
            return rec

        sha1 = hashlib.sha1(content).hexdigest()
        with self._lock:
            if sha1 in self.seen_hashes:
                rec = DownloadRecord(page_url, image_url, None, sha1, len(content), content_type, "duplicate", alt)
                self._log(rec)
                return rec

            self.seen_hashes.add(sha1)
            filename = _filename_for(image_url, content_type, sha1)
            local_path = self.out_dir / filename
            if local_path.exists():
                local_path = self.out_dir / f"{sha1}_{filename}"
            local_path.write_bytes(content)

        if dims is None:
            dims = _image_dimensions(content)
        w, h = dims if dims else (None, None)

        rec = DownloadRecord(
            page_url, image_url, str(local_path), sha1, len(content), content_type, "saved", alt, w, h,
        )
        self._log(rec)
        return rec

    def download_many(self, page_url: str, candidates: list[ImageCandidate]) -> list[DownloadRecord]:
        if self.concurrency == 1:
            return [self.download_one(page_url, c) for c in candidates]
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            return list(pool.map(lambda c: self.download_one(page_url, c), candidates))
