# WebSpider

[![CI](https://github.com/khhvmc5g6f-eng/WebSpider/actions/workflows/ci.yml/badge.svg)](https://github.com/khhvmc5g6f-eng/WebSpider/actions/workflows/ci.yml)

A polite, research-oriented web crawler — image discovery/download **and**
text/data extraction, combining the useful parts of several single-purpose
scrapers into one tool, plus a [Claude Code skill](SKILL.md) wrapper so it can
be driven directly from Claude Code.

## What it does

**Images:**
- **Scrape** a single page for images (`<img src>`, `data-src`, `srcset`,
  `<picture><source>`, `og:image`, CSS `background-image`).
- **Crawl** a site — BFS over internal links, collecting images from every page
  it visits, capped by `--max-pages` / `--max-depth`.
- **Dedup** downloads by content SHA-1 hash, and log every attempt (saved /
  duplicate / skipped / error) — plus alt text and dimensions — to a
  `manifest.jsonl`.
- Optional **dimension filtering** (`--min-width`/`--min-height`, needs the
  `[images]` extra) to skip icons/tracking pixels.

**Text & data** (the non-image counterpart — needs the `[text]` extra):
- **`webspider extract <url>`** — clean article text, Markdown (tables included),
  page metadata (author/date/sitename/language), embedded structured data
  (schema.org JSON-LD, microdata, OpenGraph), and generic **labeled fields**
  pulled from tables/definition-lists/bolded labels — this last one is what
  catches guide-style content like "Hazards: ..." or "Wind window: ..." that
  structured-data formats don't expose at all, since it works off the page's
  own labels rather than a fixed schema.
- `webspider crawl --extract` / `webspider batch --extract` run the same
  extraction across a whole site or URL list, writing one JSON record per page
  to `content.jsonl`. Add `--no-images` to skip image downloading entirely when
  all you want is content.

**Both:**
- **Batch** process a file of URLs — pages to scrape/extract, or a list of
  direct image URLs to download.
- Handle **JS-rendered pages** via optional headless Chromium (Playwright), with
  an `--render-auto` heuristic that retries with rendering only when a static
  fetch looks like an empty SPA shell.
- **Map** a site fast (`webspider map`) — sitemap.xml/robots.txt discovery with a
  link-crawl fallback, no downloads, to scope a crawl before running it.
- **Concurrent downloads** (`--concurrency`) and **resumable runs** (`--resume`)
  that skip already-processed pages/images from a prior run.
- Scope image discovery to a **CSS selector** (`--selector`) to ignore site chrome.
- **Respect `robots.txt`** — both disallow rules and the site's requested
  `Crawl-delay` — and rate-limit requests by default.
- Optional **cookie-file support** (`--cookies-file`) so WebSpider can act as the
  user's own already-logged-in session — not a bypass, only for accounts the
  user already has access to.

## What it deliberately does *not* do

WebSpider does not include CAPTCHA solving, Cloudflare/WAF/Turnstile bypass,
browser-fingerprint spoofing, or paywall circumvention. If a site is actively
blocking automated access or requires payment, WebSpider skips/logs it rather
than fighting past it — those protections are the site owner's explicit
"no automated access" signal, and defeating them is out of scope regardless of
the reason for scraping. Check for an official API or bulk-data export instead.

## Install

```bash
git clone https://github.com/khhvmc5g6f-eng/WebSpider
cd WebSpider
pip install -e .

# optional, for JS-rendered pages:
pip install -e '.[render]'
playwright install chromium

# optional, for dimension filtering:
pip install -e '.[images]'

# optional, for text/data extraction:
pip install -e '.[text]'
```

## Usage

```bash
webspider map https://example.com --out urls.txt                    # fast recon, no downloads
webspider scrape https://example.com/gallery --out ./out
webspider crawl https://example.com --out ./out --max-pages 50 --max-depth 3
webspider crawl https://example.com --concurrency 8 --resume         # faster, interruption-safe
webspider batch urls.txt --out ./out                 # urls.txt = pages to scrape
webspider batch urls.txt --out ./out --raw-images     # urls.txt = direct image URLs
webspider crawl https://example.com --render          # JS-heavy site
webspider crawl https://example.com --render-auto     # only render pages that look JS-dependent

# text/data extraction (needs [text])
webspider extract https://example.com/page --out record.json
webspider crawl https://example.com --extract --no-images --max-pages 50   # site-wide, content only
webspider batch urls.txt --extract --no-images                             # from a URL list
```

Run `webspider <command> --help` for the full option list (delay, user-agent,
same-domain restriction, robots.txt toggle, etc.).

## As a Claude Code skill

This repo's [SKILL.md](SKILL.md) documents when/how Claude Code should invoke
the CLI. Point Claude Code at a checkout of this repo (or add it as a plugin
skill) to use it directly from a conversation.

## Known limitations

- `robots.txt` parsers are cached per-domain for the life of the process and
  never refreshed. Irrelevant for the CLI's normal one-shot runs; would matter
  if WebSpider were ever embedded as a library in a long-lived process.
- `.crawl_state.json` (used by `--resume`) isn't pruned — a crawl spanning many
  thousands of pages will accumulate a correspondingly large state file.
- JSON-LD wrapped in an HTML comment (`<script type="application/ld+json"><!--{...}--></script>`,
  an old browser-compat pattern) isn't parsed.
- `extract_labeled_fields` is a heuristic, not a schema — it finds whatever
  labels a page happens to use, so field *names* will vary page to page (a
  guide site's own template consistency is what makes this useful in practice,
  not a hardcoded field list). RDFa is excluded from `extract_structured_data`
  by default (very noisy on many real sites) — pass `syntaxes=[..., "rdfa"]`
  if you need it.

## Roadmap / not yet implemented

- Perceptual/near-duplicate hashing (catch recompressed or resized copies that
  exact SHA-1 dedup misses) — considered, not built yet.
- Parquet/WebDataset export for large-scale dataset pipelines (see
  [img2dataset](https://github.com/rom1504/img2dataset) if you need this now).

## Development

```bash
pip install -e '.[dev]'
pytest
```

## License

MIT — see [LICENSE](LICENSE).
