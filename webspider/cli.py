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
@click.option("--summarize", "do_summarize", is_flag=True, default=False, help="Also turn the extracted content into a summary card via an LLM (needs webspider[ai] + ANTHROPIC_API_KEY).")
@click.option("--model", default=None, help="Model to use for --summarize (default: webspider.summarize.DEFAULT_MODEL).")
@_common_fetch_options
def extract(url, out_file, render, do_summarize, model, user_agent, cookies_file):
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
    if do_summarize:
        from .summarize import DEFAULT_MODEL, summarize_record
        try:
            record["summary_card"] = summarize_record(record, model=model or DEFAULT_MODEL)
        except RuntimeError as e:
            raise click.ClickException(str(e)) from e

    output = json.dumps(record, indent=2)
    if out_file:
        Path(out_file).write_text(output)
        click.echo(f"Written to {out_file}")
    else:
        click.echo(output)


@main.command()
@click.argument("content_file", type=click.Path(exists=True))
@click.option("--out", "out_file", default=None, type=click.Path(), help="Write summary cards (one JSON per line) here instead of stdout.")
@click.option("--model", default=None, help="Model to use (default: webspider.summarize.DEFAULT_MODEL).")
@click.option("--limit", default=None, type=int, help="Only summarize the first N records (useful to sanity-check cost/quality before a full run).")
@click.option("--instructions", default="", help="Extra instructions appended to every summarization prompt.")
def summarize(content_file, out_file, model, limit, instructions):
    """Turn each record in a content.jsonl (from `extract`/`crawl --extract`/`batch --extract`)
    into a clean summary card via an LLM — e.g. for rendering in your own app.
    Needs webspider[ai] + ANTHROPIC_API_KEY. Cards are explicitly generated content,
    faithful to the source but never presented as the original page's own text."""
    from .summarize import DEFAULT_MODEL, summarize_record
    try:
        import anthropic
    except ImportError as e:
        raise click.ClickException(
            "Summarization requires the optional dependency. Install with: "
            "pip install 'webspider[ai]', and set ANTHROPIC_API_KEY."
        ) from e

    client = anthropic.Anthropic()
    lines = Path(content_file).read_text(encoding="utf-8").splitlines()
    if limit:
        lines = lines[:limit]

    out_lines = []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        record = json.loads(line)
        try:
            card = summarize_record(record, model=model or DEFAULT_MODEL, extra_instructions=instructions, client=client)
        except Exception as e:
            click.echo(f"[{i}/{len(lines)}] skip {record.get('url')}: {e}")
            continue
        out_lines.append(json.dumps(card))
        click.echo(f"[{i}/{len(lines)}] {card.get('title') or record.get('url')}")

    output = "\n".join(out_lines) + ("\n" if out_lines else "")
    if out_file:
        Path(out_file).write_text(output)
        click.echo(f"Written {len(out_lines)} cards to {out_file}")
    else:
        click.echo(output)


@main.command()
@click.argument("source", type=click.File("r", encoding="utf-8"))
@click.option("--out", "out_file", default=None, type=click.Path(), help="Write the revised text or JSON report to this file.")
@click.option("--profile", type=click.Choice(["plain", "professional", "editorial", "concise"]), default="plain", show_default=True)
@click.option("--voice-sample", type=click.Path(exists=True, dir_okay=False), default=None, help="Optional writing sample used only for cadence, formality, and vocabulary level.")
@click.option("--model", default=None, help="Model to use (default: webspider.humanize.DEFAULT_MODEL).")
@click.option("--audit-only", is_flag=True, help="Run deterministic writing diagnostics without calling an LLM.")
@click.option("--json-output", is_flag=True, help="Emit the full audit, integrity, and provenance report as JSON.")
def humanize(source, out_file, profile, voice_sample, model, audit_only, json_output):
    """Improve a text file's clarity and natural rhythm without changing facts.

    SOURCE may be '-' for stdin. The command preserves exact numbers, dates,
    measurements, URLs, emails, and quotations, and fails closed if they drift.
    It is an editorial tool, not an AI detector or detector-evasion feature.
    """
    from .humanize import DEFAULT_MODEL, HumanizationIntegrityError, audit_text, humanize_text

    source_text = source.read()
    if not source_text.strip():
        raise click.ClickException("Source text is empty.")

    if audit_only:
        result = audit_text(source_text)
        output = json.dumps(result, indent=2)
    else:
        sample = Path(voice_sample).read_text(encoding="utf-8") if voice_sample else ""
        try:
            result = humanize_text(source_text, profile=profile, voice_sample=sample, model=model or DEFAULT_MODEL)
        except (RuntimeError, ValueError, HumanizationIntegrityError) as exc:
            raise click.ClickException(str(exc)) from exc
        output = json.dumps(result, indent=2) if json_output else result["text"]

    if out_file:
        Path(out_file).write_text(output + ("" if output.endswith("\n") else "\n"), encoding="utf-8")
        click.echo(f"Written to {out_file}")
    else:
        click.echo(output)


@main.command()
@click.argument("url")
@click.option("--out", "out_file", default=None, type=click.Path(), help="Write the result as JSON to this file instead of stdout.")
@click.option("--capture-network/--no-capture-network", default=False, help="Also load the page in a headless browser and record its own JSON API calls (needs webspider[render]).")
@click.option("--user-agent", default=DEFAULT_USER_AGENT)
def inspect(url, out_file, capture_network, user_agent):
    """Find images/links present in a page's own code or network traffic that
    never make it into the rendered DOM: embedded framework hydration state
    (Next.js __NEXT_DATA__, best-effort Nuxt/generic window.__X__ blobs), and
    optionally the JSON API responses the page's own JS calls on a normal load.
    This reads what a real page load already fetches — it does not probe for
    undocumented endpoints. Use this when discover.py's DOM scan seems to be
    missing content you know the site has (extra images, extra fields, source
    links not rendered as clickable <a> tags)."""
    from .inspect import inspect_page

    result = fetch_static(url, user_agent=user_agent)
    if result.status != 200 or not result.text:
        raise click.ClickException(f"Fetch failed: HTTP {result.status}")

    try:
        record = inspect_page(result.text, url, capture_network=capture_network, user_agent=user_agent)
    except RuntimeError as e:
        raise click.ClickException(str(e)) from e

    click.echo(f"Embedded state blocks found: {record['embedded_state_keys'] or 'none'}")
    if capture_network:
        click.echo(f"JSON network responses captured: {len(record['network_responses'])}")
    click.echo(f"Images found beyond the DOM: {len(record['discovered_images'])}")
    click.echo(f"Links found beyond the DOM: {len(record['discovered_links'])}")

    output = json.dumps(record, indent=2)
    if out_file:
        Path(out_file).write_text(output)
        click.echo(f"Written to {out_file}")
    else:
        click.echo(output)


if __name__ == "__main__":
    main()
