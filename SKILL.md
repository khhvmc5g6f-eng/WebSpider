---
name: webspider
description: Crawl websites for research — image discovery/download AND text/data extraction. Fast URL mapping (sitemap.xml), single-page scrape/extract, site-wide crawl following internal links, or batch processing a list of URLs. Extraction pulls clean text/Markdown/tables/metadata (trafilatura), embedded structured data (JSON-LD/microdata/OpenGraph via extruct), and generic labeled fields from tables/definition-lists/bolded labels (e.g. a guide page's "Hazards:"/"Wind window:" fields) — the extraction path Claude's own WebFetch doesn't give you as structured, savable JSON. Handles static and JS-rendered pages, concurrent + resumable runs, dedups images by content hash, respects robots.txt (including Crawl-delay) and rate limits. Does NOT bypass CAPTCHAs, Cloudflare/WAF challenges, or paywalls — use for openly accessible pages only.
---

# WebSpider

A polite, research-oriented web crawler — image discovery/download AND text/data
extraction. Use this skill when the user wants to pull images, or pull
structured content (article text, tables, metadata, guide-style labeled
fields), from one page, a whole site, or a list of URLs, for research/
dataset-building purposes on openly accessible pages.

## When to use

- "Download all the images from this page/site"
- "Crawl this site and collect its images for a dataset"
- "Batch-download images from this list of URLs"
- "Extract the [text/tables/metadata/hazards/specs/...] from this page"
- "Crawl this site and pull out [guide content / article text / structured data]
  from every page" — e.g. a directory of site guides where each page lists
  fields like hazards, wind direction, access notes, etc. in a table or
  definition list

## When NOT to use

- The target site requires a login/paywall the user doesn't have legitimate access to.
- The target site is protected by Cloudflare/WAF/CAPTCHA and returns a challenge page —
  this tool will skip it rather than fight past it. Check for an official API or bulk
  data export instead.

## Usage

Install once: `pip install -e .` from the repo root. Extras: `[render]` for
JS-heavy pages (`pip install -e '.[render]' && playwright install chromium`),
`[images]` for dimension filtering, `[text]` for extraction (`pip install -e
'.[text]'` — needed for every `extract` command/flag below).

```bash
# Single page: images
webspider scrape https://example.com/gallery --out ./out

# Single page: text/tables/metadata/structured-data/labeled-fields (needs [text])
webspider extract https://example.com/site-guide/some-site --out record.json

# Site-wide crawl: images (follows internal links, same domain by default)
webspider crawl https://example.com --out ./out --max-pages 50 --max-depth 3

# Site-wide crawl: content only, no images — the shape most content-extraction
# tasks want (e.g. a directory of guide pages, each with its own fields)
webspider crawl https://example.com --extract --no-images --max-pages 100 --out ./out

# Batch: file of page URLs (one per line) -> scrape each for images
webspider batch urls.txt --out ./out

# Batch: file of page URLs -> extract content from each, no images
webspider batch urls.txt --extract --no-images --out ./out

# Batch: file of direct image URLs -> download each
webspider batch urls.txt --out ./out --raw-images

# JS-heavy site: render with headless Chromium instead of static HTML
webspider crawl https://example.com --render

# Fast recon before a big crawl/extract run: just list URLs (sitemap.xml, or a
# link-crawl fallback) — this is the "map" half of the map->extract workflow
webspider map https://example.com --out urls.txt

# Faster: 8 concurrent download workers, resumable if interrupted
webspider crawl https://example.com --concurrency 8 --resume

# Scope image discovery to a gallery container only, skip nav/footer icons
webspider scrape https://example.com/page --selector ".gallery"
```

Every image run writes `manifest.jsonl` to the output directory: one JSON
record per image with its source page, URL, local path, sha1, alt text,
dimensions (if `[images]` extra installed), and status
(`saved`/`duplicate`/`skipped`/`error`). Duplicate images (by content hash) are
detected and not re-saved within a run. `--resume` makes a `crawl`/`batch`/
`scrape` skip images already recorded from a prior run in the same `--out`
directory.

Every `--extract` run writes `content.jsonl` to the output directory: one JSON
record per page — `url`, `title`, `text`, `markdown` (tables included as
Markdown pipe-tables), `metadata` (author/date/sitename/hostname/language),
`structured_data` (JSON-LD/microdata/OpenGraph), and `labeled_fields` (a flat
`{label: value}` dict pulled from that page's own tables/definition-lists/
bolded labels — the part that catches a site guide's "Hazards"/"Wind window"
style fields, since those virtually never show up in schema.org markup).
`labeled_fields` keys are whatever the page itself uses, not a fixed schema —
expect them to vary across sites, or even across pages on the same site if its
template isn't consistent.

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
- `webspider/extract.py` — text/Markdown/metadata (trafilatura), structured
  data (extruct: JSON-LD/microdata/OpenGraph), and the hand-rolled
  `extract_labeled_fields()` (definition lists, two-column tables, inline bold
  labels) — the non-schema.org content most guide pages actually use.
- `webspider/cli.py` — `scrape` / `crawl` / `batch` / `map` / `extract` commands.
