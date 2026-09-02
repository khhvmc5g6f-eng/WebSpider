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
- **`webspider inspect <url>`** — finds images/links present in a page's own
  code or network traffic that never reach the rendered DOM: embedded
  framework hydration state (Next.js `__NEXT_DATA__`, best-effort Nuxt/generic
  `window.__X__` blobs), plus — with `--capture-network` (needs `[render]`) —
  the JSON API responses the page's own JS calls on a normal load. This reads
  what a real page load already fetches; it does not probe for undocumented
  endpoints. Use it when `extract`/`scrape` seem to be missing content you
  know the site has.
- **`webspider summarize <content.jsonl>`** — turns each extracted record into
  a clean summary card (title/summary/key_facts/tags) via an LLM, for
  rendering in your own app (needs `[ai]` + `ANTHROPIC_API_KEY`). Cards are
  explicitly generated content, instructed never to invent facts beyond the
  source — see the system prompt in `webspider/summarize.py`. `webspider
  extract --summarize` does this for a single page in one step.
- **`webspider humanize <file>`** — revises generated or owned text for clearer,
  more natural prose. It supports plain, professional, editorial, and concise
  profiles plus an optional voice sample. A deterministic audit explains stock
  phrasing, rhythm, repeated openings, and long sentences. Exact numbers, dates,
  measurements, URLs, email addresses, and quotations are source-locked; the
  command fails rather than releasing a revision when those anchors drift.

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

The editorial revision feature does not estimate authorship, promise detector
outcomes, or disguise provenance. `summarize` and `humanize` produce clearly
labelled generated or AI-assisted content. Only revise text you own or have the
right to adapt, and keep the provenance metadata when publishing it.

`inspect`'s embedded-state/network-capture reads only what a page's own normal
load already fetches — it's a content-discovery tool, not an endpoint-scanning
one, and it doesn't probe for undocumented functionality the way security
recon tools (e.g. LinkFinder-style JS-endpoint extractors) do.

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

# optional, for LLM summary cards (needs ANTHROPIC_API_KEY too):
pip install -e '.[ai]'
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

# find data/images/links a DOM-only scan misses (needs [render] for --capture-network)
webspider inspect https://example.com/page --out record.json
webspider inspect https://example.com/page --capture-network

# LLM summary cards from extracted content (needs [ai] + ANTHROPIC_API_KEY)
webspider extract https://example.com/page --summarize --out record.json
webspider summarize content.jsonl --out cards.jsonl --limit 5   # sanity-check before a full run

# source-faithful editorial revision (needs [ai]); use '-' to read stdin
webspider humanize draft.txt --profile professional --out revised.txt
webspider humanize draft.txt --voice-sample my-writing.txt --json-output --out revision.json

# deterministic diagnostics only: no API key or LLM call
webspider humanize draft.txt --audit-only
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
- `inspect`'s embedded-state extraction reliably parses Next.js `__NEXT_DATA__`
  (always plain JSON by framework design) but is best-effort for Nuxt/generic
  `window.__X__` patterns — older Nuxt serializes state as a JS function call
  with variable substitution, not pure JSON, and those are skipped rather than
  mis-parsed. Modern Next.js App Router sites (13+) mostly don't emit
  `__NEXT_DATA__` at all (they stream React Server Component payloads instead,
  a different format this doesn't parse) — verified live against nextjs.org,
  which found nothing, versus github.com's `client-env` JSON block, which
  parsed correctly.
- `--capture-network` only sees JSON responses that actually arrive before
  Playwright's `networkidle` wait completes — a page that lazy-loads data on
  scroll/interaction won't have that data captured.

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
