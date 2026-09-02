---
name: webspider
description: Crawl websites and download images for research — fast URL mapping (sitemap.xml), single-page scrape, site-wide crawl following internal links, or batch processing a list of URLs. Handles static and JS-rendered pages, concurrent + resumable downloads, dedups by content hash, extracts alt text and schema.org JSON-LD image metadata, respects robots.txt (including Crawl-delay) and rate limits. Does NOT bypass CAPTCHAs, Cloudflare/WAF challenges, or paywalls — use for openly accessible pages only.
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

# Fast recon before a big crawl: just list URLs (sitemap.xml, or a link-crawl fallback)
webspider map https://example.com --out urls.txt

# Faster: 8 concurrent download workers, resumable if interrupted
webspider crawl https://example.com --concurrency 8 --resume

# Scope discovery to a gallery container only, skip nav/footer icons
webspider scrape https://example.com/page --selector ".gallery"
```

Every run writes `manifest.jsonl` to the output directory: one JSON record per
image with its source page, URL, local path, sha1, alt text, dimensions (if
`[images]` extra installed), and status (`saved`/`duplicate`/`skipped`/`error`).
Duplicate images (by content hash) are detected and not re-saved within a run.
`--resume` makes a `crawl` skip pages/images already recorded from a prior run
in the same `--out` directory.

## Politeness defaults (don't disable without a reason)

- `robots.txt` is checked before fetching each URL (`--ignore-robots` to skip, but
  don't unless the user owns the target or has explicit permission). The site's
  own requested `Crawl-delay` is honored too, not just `Disallow` rules.
- A fixed delay runs between requests (`--delay`, default 0.5s, applied per
  concurrent worker if `--concurrency` > 1).
- Crawls are capped by `--max-pages` and `--max-depth` so a run can't runaway across
  an entire domain by accident.
- The User-Agent identifies the tool by default; only override it if the user has
  a specific, legitimate reason to.
- `--cookies-file` lets WebSpider act as the user's own already-logged-in session
  (Netscape cookies.txt) — this is not a bypass mechanism, only use it for
  accounts the user already has legitimate access to.

## Architecture

- `webspider/fetch.py` — static fetch (requests, retry/backoff, optional cookie
  jar) and optional headless-Chromium rendering (Playwright, no stealth/fingerprint
  spoofing). `looks_js_dependent()` is a heuristic used by `--render-auto`.
- `webspider/discover.py` — finds image URLs + alt text (`img[src]`, `data-src`,
  `srcset`, `<picture><source>`, `og:image`, CSS `background-image`, schema.org
  JSON-LD `ImageObject`) and internal links; supports scoping to a CSS selector.
- `webspider/download.py` — concurrent downloads, hashing, dedup, optional
  Pillow-based dimension filtering, resumable manifest logging.
- `webspider/crawl.py` — BFS site crawl wiring the above together, honoring
  robots.txt Crawl-delay and supporting `--resume`.
- `webspider/robots.py` — robots.txt disallow + crawl-delay, cached per domain.
- `webspider/sitemap.py` — fast URL discovery via robots.txt `Sitemap:` +
  sitemap.xml (incl. sitemap indexes), with a link-crawl fallback. Powers `map`.
- `webspider/cli.py` — `scrape` / `crawl` / `batch` / `map` commands.
