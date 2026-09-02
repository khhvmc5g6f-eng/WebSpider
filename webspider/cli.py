"""WebSpider CLI: scrape, crawl, and batch-download images politely."""
from __future__ import annotations

from pathlib import Path

import click

from .crawl import crawl as run_crawl
from .discover import find_image_urls
from .download import Downloader
from .fetch import DEFAULT_USER_AGENT, fetch_rendered, fetch_static


def _summarize(records) -> None:
    saved = sum(1 for r in records if r.status == "saved")
    dup = sum(1 for r in records if r.status == "duplicate")
    skipped = sum(1 for r in records if r.status == "skipped")
    errors = sum(1 for r in records if r.status == "error")
    click.echo(f"saved={saved} duplicate={dup} skipped={skipped} error={errors}")


@click.group()
@click.version_option()
def main():
    """WebSpider: a polite, research-oriented web/image crawler."""


@main.command()
@click.argument("url")
@click.option("--out", "out_dir", default="./webspider_out", help="Output directory.")
@click.option("--render/--no-render", default=False, help="Use headless Chromium (Playwright) for JS-heavy pages.")
@click.option("--user-agent", default=DEFAULT_USER_AGENT)
@click.option("--delay", default=0.5, help="Seconds to wait between downloads.")
def scrape(url: str, out_dir: str, render: bool, user_agent: str, delay: float):
    """Scrape all images from a single page."""
    fetch = fetch_rendered if render else fetch_static
    result = fetch(url, user_agent=user_agent)
    if result.status != 200 or not result.text:
        raise click.ClickException(f"Fetch failed: HTTP {result.status}")
    image_urls = find_image_urls(result.text, url)
    click.echo(f"Found {len(image_urls)} candidate images on {url}")
    downloader = Downloader(Path(out_dir), user_agent=user_agent, delay=delay)
    records = downloader.download_many(url, image_urls)
    _summarize(records)
    click.echo(f"Manifest: {downloader.manifest_path}")


@main.command()
@click.argument("url")
@click.option("--out", "out_dir", default="./webspider_out", help="Output directory.")
@click.option("--max-pages", default=25, help="Stop after this many pages.")
@click.option("--max-depth", default=2, help="Max link-following depth from the start URL.")
@click.option("--same-domain/--any-domain", default=True, help="Restrict crawl to the start URL's domain.")
@click.option("--render/--no-render", default=False, help="Use headless Chromium for JS-heavy pages.")
@click.option("--user-agent", default=DEFAULT_USER_AGENT)
@click.option("--delay", default=0.5, help="Seconds to wait between requests.")
@click.option("--respect-robots/--ignore-robots", default=True)
def crawl(
    url: str,
    out_dir: str,
    max_pages: int,
    max_depth: int,
    same_domain: bool,
    render: bool,
    user_agent: str,
    delay: float,
    respect_robots: bool,
):
    """Crawl a site (following internal links) and download images from every page visited."""
    downloader = Downloader(Path(out_dir), user_agent=user_agent, delay=delay)
    result = run_crawl(
        url,
        downloader,
        max_pages=max_pages,
        max_depth=max_depth,
        same_domain=same_domain,
        render=render,
        delay=delay,
        user_agent=user_agent,
        respect_robots=respect_robots,
    )
    click.echo(f"Pages crawled: {result['pages_crawled']}")
    if result["skipped_robots"]:
        click.echo(f"Skipped (robots.txt disallow): {len(result['skipped_robots'])}")
    _summarize(result["records"])
    click.echo(f"Manifest: {downloader.manifest_path}")


@main.command()
@click.argument("url_file", type=click.Path(exists=True))
@click.option("--out", "out_dir", default="./webspider_out", help="Output directory.")
@click.option("--raw-images/--pages", default=False, help="Treat each line as a direct image URL instead of a page to scrape.")
@click.option("--render/--no-render", default=False)
@click.option("--user-agent", default=DEFAULT_USER_AGENT)
@click.option("--delay", default=0.5)
def batch(url_file: str, out_dir: str, raw_images: bool, render: bool, user_agent: str, delay: float):
    """Process a text file of URLs (one per line): pages to scrape, or direct image URLs."""
    urls = [line.strip() for line in Path(url_file).read_text().splitlines() if line.strip()]
    downloader = Downloader(Path(out_dir), user_agent=user_agent, delay=delay)
    all_records = []

    if raw_images:
        all_records = downloader.download_many(url_file, urls)
    else:
        fetch = fetch_rendered if render else fetch_static
        for page_url in urls:
            try:
                result = fetch(page_url, user_agent=user_agent)
            except Exception as e:
                click.echo(f"skip {page_url}: {e}")
                continue
            if result.status != 200 or not result.text:
                continue
            image_urls = find_image_urls(result.text, page_url)
            all_records.extend(downloader.download_many(page_url, image_urls))

    _summarize(all_records)
    click.echo(f"Manifest: {downloader.manifest_path}")


if __name__ == "__main__":
    main()
