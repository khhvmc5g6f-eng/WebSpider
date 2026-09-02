"""WebSpider CLI: scrape, crawl, map, extract, and batch-process URLs politely."""
from __future__ import annotations

import json
from pathlib import Path

import click

from .crawl import crawl as run_crawl
from .discover import find_image_urls
from .download import Downloader
from .fetch import DEFAULT_USER_AGENT, fetch_rendered, fetch_static
from .sitemap import discover_urls


def _require_text_extras() -> None:
    try:
        import extruct  # noqa: F401
        import trafilatura  # noqa: F401
    except ImportError as e:
        raise click.ClickException(
            "Text/data extraction requires the optional dependency. Install with: "
            "pip install 'webspider[text]'"
        ) from e


def _summarize(records) -> None:
    saved = sum(1 for r in records if r.status == "saved")
    dup = sum(1 for r in records if r.status == "duplicate")
    skipped = sum(1 for r in records if r.status == "skipped")
    errors = sum(1 for r in records if r.status == "error")
    click.echo(f"saved={saved} duplicate={dup} skipped={skipped} error={errors}")


def _common_fetch_options(f):
    f = click.option("--user-agent", default=DEFAULT_USER_AGENT)(f)
    f = click.option("--cookies-file", default=None, help="Netscape-format cookies.txt for your OWN logged-in session (not a bypass — same as opening the page in your browser).")(f)
    return f


def _common_download_options(f):
    f = click.option("--delay", default=0.5, help="Seconds to wait between downloads (per worker).")(f)
    f = click.option("--concurrency", default=1, help="Parallel download workers.")(f)
    f = click.option("--min-width", default=None, type=int, help="Skip images narrower than this (requires Pillow: pip install webspider[images]).")(f)
    f = click.option("--min-height", default=None, type=int, help="Skip images shorter than this (requires Pillow).")(f)
    f = click.option("--selector", default=None, help="CSS selector to scope image discovery to (e.g. '.gallery').")(f)
    f = click.option("--resume", is_flag=True, default=False, help="Skip images already recorded in --out's manifest from a previous run.")(f)
    return f


@click.group()
@click.version_option()
def main():
    """WebSpider: a polite, research-oriented web crawler — images and text/data extraction."""


@main.command()
@click.argument("url")
@click.option("--out", "out_dir", default="./webspider_out", help="Output directory.")
@click.option("--render/--no-render", default=False, help="Use headless Chromium (Playwright) for JS-heavy pages.")
@_common_fetch_options
@_common_download_options
def scrape(url, out_dir, render, user_agent, cookies_file, delay, concurrency, min_width, min_height, selector, resume):
    """Scrape all images from a single page."""
    fetch = fetch_rendered if render else fetch_static
    result = fetch(url, user_agent=user_agent, cookies_file=cookies_file)
    if result.status != 200 or not result.text:
        raise click.ClickException(f"Fetch failed: HTTP {result.status}")
    candidates = find_image_urls(result.text, url, scope_selector=selector)
    click.echo(f"Found {len(candidates)} candidate images on {url}")
    downloader = Downloader(
        Path(out_dir), user_agent=user_agent, delay=delay, concurrency=concurrency,
        cookies_file=cookies_file, min_width=min_width, min_height=min_height, resume=resume,
    )
    records = downloader.download_many(url, candidates)
    _summarize(records)
    click.echo(f"Manifest: {downloader.manifest_path}")


@main.command()
@click.argument("url")
@click.option("--out", "out_dir", default="./webspider_out", help="Output directory.")
@click.option("--max-pages", default=25, help="Stop after this many pages.")
@click.option("--max-depth", default=2, help="Max link-following depth from the start URL.")
@click.option("--same-domain/--any-domain", default=True, help="Restrict crawl to the start URL's domain.")
@click.option("--render/--no-render", default=False, help="Use headless Chromium for JS-heavy pages.")
@click.option("--render-auto", is_flag=True, default=False, help="Auto-retry with rendering when a static fetch looks JS-dependent (empty SPA shell, noscript warning).")
@click.option("--respect-robots/--ignore-robots", default=True)
@click.option("--images/--no-images", default=True, help="Download images from each page visited (on by default).")
@click.option("--extract", "extract_content", is_flag=True, default=False, help="Also extract text/markdown/metadata/structured-data/labeled-fields from each page into content.jsonl (needs webspider[text]).")
@_common_fetch_options
@_common_download_options
def crawl(
    url, out_dir, max_pages, max_depth, same_domain, render, render_auto, respect_robots, images, extract_content,
    user_agent, cookies_file, delay, concurrency, min_width, min_height, selector, resume,
):
    """Crawl a site (following internal links), downloading images and/or extracting page content."""
    if extract_content:
        _require_text_extras()
    downloader = Downloader(
        Path(out_dir), user_agent=user_agent, delay=delay, concurrency=concurrency,
        cookies_file=cookies_file, min_width=min_width, min_height=min_height, resume=resume,
    )
    result = run_crawl(
        url, downloader, max_pages=max_pages, max_depth=max_depth, same_domain=same_domain,
        render=render, render_auto=render_auto, delay=delay, user_agent=user_agent,
        respect_robots=respect_robots, scope_selector=selector, cookies_file=cookies_file, resume=resume,
        download_images=images, extract_content=extract_content,
    )
    click.echo(f"Pages crawled: {result['pages_crawled']}")
    if result["skipped_robots"]:
        click.echo(f"Skipped (robots.txt disallow): {len(result['skipped_robots'])}")
    if images:
        _summarize(result["records"])
        click.echo(f"Manifest: {downloader.manifest_path}")
    if extract_content:
        click.echo(f"Pages extracted: {result['pages_extracted']}")
        click.echo(f"Content: {result['content_path']}")


@main.command()
@click.argument("url_file", type=click.Path(exists=True))
@click.option("--out", "out_dir", default="./webspider_out", help="Output directory.")
@click.option("--raw-images/--pages", default=False, help="Treat each line as a direct image URL instead of a page to scrape.")
@click.option("--render/--no-render", default=False)
@click.option("--images/--no-images", default=True, help="Download images from each page (on by default; ignored with --raw-images, which always downloads).")
@click.option("--extract", "extract_content", is_flag=True, default=False, help="Also extract text/markdown/metadata/structured-data/labeled-fields from each page into content.jsonl (needs webspider[text]; ignored with --raw-images).")
@_common_fetch_options
@_common_download_options
def batch(url_file, out_dir, raw_images, render, images, extract_content, user_agent, cookies_file, delay, concurrency, min_width, min_height, selector, resume):
    """Process a text file of URLs (one per line): pages to scrape/extract, or direct image URLs."""
    if extract_content:
        _require_text_extras()
    urls = [line.strip() for line in Path(url_file).read_text().splitlines() if line.strip()]
    downloader = Downloader(
        Path(out_dir), user_agent=user_agent, delay=delay, concurrency=concurrency,
        cookies_file=cookies_file, min_width=min_width, min_height=min_height, resume=resume,
    )
    all_records = []
    content_path = Path(out_dir) / "content.jsonl"
    pages_extracted = 0

    if raw_images:
        from .discover import ImageCandidate
        all_records = downloader.download_many(url_file, [ImageCandidate(url=u) for u in urls])
    else:
        fetch = fetch_rendered if render else fetch_static
        for page_url in urls:
            try:
                result = fetch(page_url, user_agent=user_agent, cookies_file=cookies_file)
            except Exception as e:
                click.echo(f"skip {page_url}: {e}")
                continue
            if result.status != 200 or not result.text:
                continue
            if images:
                candidates = find_image_urls(result.text, page_url, scope_selector=selector)
                all_records.extend(downloader.download_many(page_url, candidates))
            if extract_content:
                from .extract import build_content_record
                record = build_content_record(result.text, page_url)
                with content_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
                pages_extracted += 1

    if raw_images or images:
        _summarize(all_records)
        click.echo(f"Manifest: {downloader.manifest_path}")
    if extract_content:
        click.echo(f"Pages extracted: {pages_extracted}")
        click.echo(f"Content: {content_path}")


@main.command(name="map")
@click.argument("url")
@click.option("--max-pages", default=200, help="Cap on URLs returned.")
@click.option("--any-domain", is_flag=True, default=False, help="Allow discovered URLs outside the start URL's domain (link-crawl fallback only).")
@click.option("--out", "out_file", default=None, type=click.Path(), help="Write discovered URLs (one per line) to this file instead of stdout.")
@click.option("--user-agent", default=DEFAULT_USER_AGENT)
@click.option("--respect-robots/--ignore-robots", default=True)
def map_(url, max_pages, any_domain, out_file, user_agent, respect_robots):
    """Discover URLs on a site fast (sitemap.xml, or a link-crawl fallback) — no downloads.
    Use this to scope a site before running a full `crawl`."""
    result = discover_urls(
        url, max_pages=max_pages, same_domain=not any_domain, user_agent=user_agent, respect_robots=respect_robots
    )
    click.echo(f"Source: {result['source']} — {len(result['urls'])} URLs")
    if out_file:
        Path(out_file).write_text("\n".join(result["urls"]) + "\n")
        click.echo(f"Written to {out_file}")
    else:
        for u in result["urls"]:
            click.echo(u)


@main.command()
@click.argument("url")
@click.option("--out", "out_file", default=None, type=click.Path(), help="Write the extracted record as JSON to this file instead of stdout.")
@click.option("--render/--no-render", default=False, help="Use headless Chromium (Playwright) for JS-heavy pages.")
@_common_fetch_options
def extract(url, out_file, render, user_agent, cookies_file):
    """Extract text, markdown, metadata, structured data (JSON-LD/microdata/OpenGraph),
    and generic labeled fields (tables, definition lists, bolded labels) from a single
    page — the non-image counterpart to `scrape`. Needs webspider[text]."""
    _require_text_extras()
    from .extract import build_content_record

    fetch = fetch_rendered if render else fetch_static
    result = fetch(url, user_agent=user_agent, cookies_file=cookies_file)
    if result.status != 200 or not result.text:
        raise click.ClickException(f"Fetch failed: HTTP {result.status}")

    record = build_content_record(result.text, url)
    output = json.dumps(record, indent=2)
    if out_file:
        Path(out_file).write_text(output)
        click.echo(f"Written to {out_file}")
    else:
        click.echo(output)


if __name__ == "__main__":
    main()
