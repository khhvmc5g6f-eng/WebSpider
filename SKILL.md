---
name: webspider
description: Crawl websites and download images for research — single-page scrape, site-wide crawl following internal links, or batch processing a list of URLs. Handles static and JS-rendered pages, dedups by content hash, respects robots.txt and rate limits. Does NOT bypass CAPTCHAs, Cloudflare/WAF challenges, or paywalls — use for openly accessible pages only.
---

# WebSpider

A polite, research-oriented web/image crawler. Use this skill when the user wants to
pull images or crawl a site for research/dataset-building purposes on openly
accessible pages.

## When to use

- "Download all the images from this page/site"
- "Crawl this site and collect its images for a dataset"
- "Batch-download images from this list of URLs"

## When NOT to use

- The target site requires a login/paywall the user doesn't have legitimate access to.
- The target site is protected by Cloudflare/WAF/CAPTCHA and returns a challenge page —
  this tool will skip it rather than fight past it. Check for an official API or bulk
  data export instead.

## Usage

Install once: `pip install -e .` from the repo root (add `[render]` for JS pages:
`pip install -e '.[render]' && playwright install chromium`).

```bash
# Single page
webspider scrape https://example.com/gallery --out ./out

# Site-wide crawl (follows internal links, same domain by default)
webspider crawl https://example.com --out ./out --max-pages 50 --max-depth 3

# Batch: file of page URLs (one per line) -> scrape each
webspider batch urls.txt --out ./out

# Batch: file of direct image URLs -> download each
webspider batch urls.txt --out ./out --raw-images

# JS-heavy site: render with headless Chromium instead of static HTML
webspider crawl https://example.com --render
```

Every run writes `manifest.jsonl` to the output directory: one JSON record per
image with its source page, URL, local path, sha1, and status
(`saved`/`duplicate`/`skipped`/`error`). Duplicate images (by content hash) are
detected and not re-saved within a run.

## Politeness defaults (don't disable without a reason)

- `robots.txt` is checked before fetching each URL (`--ignore-robots` to skip, but
  don't unless the user owns the target or has explicit permission).
- A fixed delay runs between requests (`--delay`, default 0.5s).
- Crawls are capped by `--max-pages` and `--max-depth` so a run can't runaway across
  an entire domain by accident.
- The User-Agent identifies the tool by default; only override it if the user has
  a specific, legitimate reason to.

## Architecture

- `webspider/fetch.py` — static fetch (requests, retry/backoff) and optional
  headless-Chromium rendering (Playwright, no stealth/fingerprint spoofing).
- `webspider/discover.py` — finds image URLs (`img[src]`, `data-src`, `srcset`,
  `<picture><source>`, `og:image`, CSS `background-image`) and internal links.
- `webspider/download.py` — downloads, hashes, dedups, and logs to `manifest.jsonl`.
- `webspider/crawl.py` — BFS site crawl wiring the above together.
- `webspider/robots.py` — robots.txt compliance, cached per domain.
- `webspider/cli.py` — `scrape` / `crawl` / `batch` commands.
