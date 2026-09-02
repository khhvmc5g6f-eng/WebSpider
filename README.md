# WebSpider

[![CI](https://github.com/khhvmc5g6f-eng/WebSpider/actions/workflows/ci.yml/badge.svg)](https://github.com/khhvmc5g6f-eng/WebSpider/actions/workflows/ci.yml)

A polite, research-oriented web/image crawler — combining the useful parts of
several single-purpose scrapers into one tool, plus a [Claude Code skill](SKILL.md)
wrapper so it can be driven directly from Claude Code.

## What it does

- **Scrape** a single page for images (`<img src>`, `data-src`, `srcset`,
  `<picture><source>`, `og:image`, CSS `background-image`).
- **Crawl** a site — BFS over internal links, collecting images from every page
  it visits, capped by `--max-pages` / `--max-depth`.
- **Batch** process a file of URLs — either pages to scrape, or a list of direct
  image URLs to download.
- Handle **JS-rendered pages** via optional headless Chromium (Playwright), with
  an `--render-auto` heuristic that retries with rendering only when a static
  fetch looks like an empty SPA shell.
- **Map** a site fast (`webspider map`) — sitemap.xml/robots.txt discovery with a
  link-crawl fallback, no downloads, to scope a crawl before running it.
- **Dedup** downloads by content SHA-1 hash, and log every attempt (saved /
  duplicate / skipped / error) — plus alt text and dimensions — to a
  `manifest.jsonl`.
- **Concurrent downloads** (`--concurrency`) and **resumable runs** (`--resume`)
  that skip already-processed pages/images from a prior run.
- Scope discovery to a **CSS selector** (`--selector`) to ignore site chrome, and
  pull images out of **schema.org JSON-LD** (`ImageObject`) as well as HTML.
- **Respect `robots.txt`** — both disallow rules and the site's requested
  `Crawl-delay` — and rate-limit requests by default.
- Optional **cookie-file support** (`--cookies-file`) so WebSpider can act as the
  user's own already-logged-in session — not a bypass, only for accounts the
  user already has access to.
- Optional **dimension filtering** (`--min-width`/`--min-height`, needs the
  `[images]` extra) to skip icons/tracking pixels.

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
