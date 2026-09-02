"""Text and structured-data extraction from an already-fetched HTML page.

Complements discover.py (finds images) with the other half of "read a page":
clean article text/markdown/metadata (trafilatura), embedded structured data
(extruct: JSON-LD/microdata/OpenGraph), and a generic label/value extractor
for guide-style content (tables, definition lists, bolded labels) — the kind
of thing a site guide expresses as "Hazards: ..." or "Wind window: ..." that
schema.org markup usually doesn't cover at all.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

_TEXT_EXTRA_HINT = "Install with: pip install 'webspider[text]'"


def extract_page(
    html: str,
    url: str,
    include_tables: bool = True,
    include_comments: bool = False,
) -> dict:
    """Clean main-content text + markdown + metadata via trafilatura."""
    try:
        import trafilatura
    except ImportError as e:
        raise RuntimeError(f"Text extraction requires the optional dependency. {_TEXT_EXTRA_HINT}") from e

    doc = trafilatura.bare_extraction(
        html, url=url, include_tables=include_tables, include_comments=include_comments, with_metadata=True
    )
    if doc is None:
        return {"url": url, "title": None, "text": None, "markdown": None, "metadata": {}}

    data = doc.as_dict()
    markdown = trafilatura.extract(
        html, url=url, output_format="markdown", include_tables=include_tables, include_comments=include_comments
    )
    return {
        "url": url,
        "title": data.get("title"),
        "text": data.get("text"),
        "markdown": markdown,
        "metadata": {
            k: data.get(k)
            for k in ("author", "date", "sitename", "description", "hostname", "language", "categories", "tags")
        },
    }


def extract_structured_data(html: str, url: str, syntaxes: list[str] | None = None) -> dict:
    """Embedded structured data: JSON-LD, microdata, OpenGraph. RDFa is opt-in
    (pass syntaxes=[..., "rdfa"]) — it's extremely noisy on many real sites
    (hundreds of low-value triples), so it's excluded by default."""
    try:
        import extruct
    except ImportError as e:
        raise RuntimeError(f"Structured-data extraction requires the optional dependency. {_TEXT_EXTRA_HINT}") from e
    syntaxes = syntaxes or ["json-ld", "microdata", "opengraph"]
    try:
        return extruct.extract(html, base_url=url, syntaxes=syntaxes)
    except Exception:
        return {s: [] for s in syntaxes}


def build_content_record(html: str, url: str) -> dict:
    """Bundle extract_page + extract_structured_data + extract_labeled_fields
    into one record, for writing to a content.jsonl manifest (one line per
    page) alongside — or instead of — an image manifest.jsonl."""
    page = extract_page(html, url)
    return {
        "url": url,
        "title": page["title"],
        "text": page["text"],
        "markdown": page["markdown"],
        "metadata": page["metadata"],
        "structured_data": extract_structured_data(html, url),
        "labeled_fields": extract_labeled_fields(html),
    }


def extract_labeled_fields(html: str) -> dict[str, str]:
    """Generic label->value extraction for guide/spec-style pages: definition
    lists, two-column tables (a <th>, or a bolded first cell, paired with a
    value cell), and inline '<strong>Label:</strong> value' text. No knowledge
    of specific field names — this finds whatever labels the page itself uses."""
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    fields: dict[str, str] = {}

    for dl in soup.find_all("dl"):
        for dt in dl.find_all("dt"):
            label = dt.get_text(" ", strip=True).rstrip(":")
            dd = dt.find_next_sibling("dd")
            if label and dd:
                fields.setdefault(label, dd.get_text(" ", strip=True))

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) != 2:
                continue
            label_cell, value_cell = cells
            is_label_cell = label_cell.name == "th" or label_cell.find(["strong", "b"]) is not None
            if not is_label_cell:
                continue
            label = label_cell.get_text(" ", strip=True).rstrip(":")
            value = value_cell.get_text(" ", strip=True)
            if label and value:
                fields.setdefault(label, value)

    for tag in soup.find_all(["p", "li"]):
        strong = tag.find(["strong", "b"])
        if not strong:
            continue
        marker = strong.get_text(" ", strip=True)
        if not marker.endswith(":"):
            continue
        label = marker.rstrip(":")
        full_text = tag.get_text(" ", strip=True)
        idx = full_text.find(marker)
        if idx == -1:
            continue
        value = full_text[idx + len(marker):].strip(" :")
        if label and value:
            fields.setdefault(label, value)

    return fields
