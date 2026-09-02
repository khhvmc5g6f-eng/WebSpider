---
name: webspider
description: Crawl websites for research, extract structured content, create source-faithful summary cards, and revise owned or generated text for natural clarity with deterministic quality and integrity checks. Supports fast URL mapping, single-page or site-wide extraction, image discovery/download, embedded-state inspection, optional LLM summarisation, and editorial profiles with optional voice matching. Respects robots.txt and rate limits; never bypasses access controls or promises AI-detector outcomes.
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
- "Find images/data on this page that aren't showing up in the rendered content"
  — a modern framework's own embedded state or API calls often carry more
  than what the DOM renders
- "Turn this extracted content into a clean summary card for my app"
- "Make this generated or owned draft sound clearer and more natural without
  changing its facts"

## When NOT to use

- The target site requires a login/paywall the user doesn't have legitimate access to.
- The target site is protected by Cloudflare/WAF/CAPTCHA and returns a challenge page —
  this tool will skip it rather than fight past it. Check for an official API or bulk
  data export instead.

## Usage

Install once: `pip install -e .` from the repo root. Extras: `[render]` for
JS-heavy pages and `inspect --capture-network` (`pip install -e '.[render]'
&& playwright install chromium`), `[images]` for dimension filtering, `[text]`
for extraction (`pip install -e '.[text]'` — needed for every `extract`
command/flag below), `[ai]` for `summarize` and `humanize` (needs
`ANTHROPIC_API_KEY` too).

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

# Find data/images/links a DOM-only scan misses (embedded framework state;
# add --capture-network for the page's own JSON API calls, needs [render])
webspider inspect https://example.com/page --capture-network --out record.json

# Turn extracted content into a summary card (needs [ai] + ANTHROPIC_API_KEY)
webspider extract https://example.com/page --summarize --out record.json
webspider summarize content.jsonl --out cards.jsonl --limit 5

# Editorial revision with exact-value/quotation integrity checks
webspider humanize draft.txt --profile professional --out revised.txt
webspider humanize draft.txt --voice-sample my-writing.txt --json-output

# Deterministic editorial diagnostics only, without an LLM call
webspider humanize draft.txt --audit-only
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

`inspect` writes `embedded_state` (raw parsed framework state blobs, keyed by
the variable/script-id they came from), `network_responses` (if
`--capture-network`), and `discovered_images`/`discovered_links` — URLs found
inside that data, resolved to absolute and deduped against nothing else (diff
these against a DOM-based `scrape`/`extract` run yourself to see what's
actually new). This reads what a normal page load already fetches; it is not
an endpoint scanner and does not probe for undocumented functionality.

`summarize` (and `extract --summarize`) call an LLM per page and cost real
tokens — use `--limit` to sanity-check quality/cost on a few records before
running it across a whole `content.jsonl`. The output `key_facts` are
instructed to reuse the source's own `labeled_fields` rather than reinterpret
them, and `summary` is instructed never to invent facts not in the source —
but it's still generated content: present it to the end user as a summary,
not as the original page's text.

`humanize` is a source-faithful editorial tool, not an authorship detector. Its
quality score reports explainable prose signals only. The LLM prompt forbids
new facts and artificial quirks; a local guard compares repeated numbers,
dates, measurements, URLs, emails, and quotations and fails closed if any
change. `--voice-sample` uses cadence, formality, and vocabulary level only,
not the sample's facts or distinctive phrases. Keep the JSON provenance report
when traceability matters.

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
- `webspider/inspect.py` — embedded framework hydration state (Next.js
  `__NEXT_DATA__`, best-effort Nuxt/generic `window.__X__`), optional
  Playwright network-response capture, and URL discovery inside that data.
- `webspider/summarize.py` — turns an `extract` record into an LLM summary card
  (title/summary/key_facts/tags), instructed to stay faithful to the source.
- `webspider/humanize.py` — natural-language revision, optional voice matching,
  deterministic quality diagnostics, and source-integrity comparison.
- `webspider/cli.py` — `scrape` / `crawl` / `batch` / `map` / `extract` /
  `inspect` / `summarize` / `humanize` commands.
