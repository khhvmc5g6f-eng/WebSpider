# WebSpider

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
- Handle **JS-rendered pages** via optional headless Chromium (Playwright).
- **Dedup** downloads by content SHA-1 hash, and log every attempt (saved /
  duplicate / skipped / error) to a `manifest.jsonl`.
- **Respect `robots.txt`** and rate-limit requests by default.

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
```

## Usage

```bash
webspider scrape https://example.com/gallery --out ./out
webspider crawl https://example.com --out ./out --max-pages 50 --max-depth 3
webspider batch urls.txt --out ./out                 # urls.txt = pages to scrape
webspider batch urls.txt --out ./out --raw-images     # urls.txt = direct image URLs
webspider crawl https://example.com --render          # JS-heavy site
```

Run `webspider <command> --help` for the full option list (delay, user-agent,
same-domain restriction, robots.txt toggle, etc.).

## As a Claude Code skill

This repo's [SKILL.md](SKILL.md) documents when/how Claude Code should invoke
the CLI. Point Claude Code at a checkout of this repo (or add it as a plugin
skill) to use it directly from a conversation.

## Development

```bash
pip install -e '.[dev]'
pytest
```

## License

MIT — see [LICENSE](LICENSE).
