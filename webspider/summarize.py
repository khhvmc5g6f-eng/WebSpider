"""Turn an extracted content record (from extract.build_content_record) into
a clean, structured "summary card" via an LLM — e.g. for rendering as a card
in the user's own app. Output is explicitly a generated summary derived from
the source, never presented as the original page's own text."""
from __future__ import annotations

import json
from datetime import datetime, timezone

_AI_EXTRA_HINT = "Install with: pip install 'webspider[ai]', and set ANTHROPIC_API_KEY."

DEFAULT_MODEL = "claude-sonnet-5"

_SYSTEM_PROMPT = """You turn one page's extracted content into a compact, factual summary card.

Rules:
- Use ONLY the material given to you (text, labeled fields, structured data). Never invent facts, numbers, or details not present in the source.
- If the source doesn't mention something, omit that field rather than guessing.
- key_facts should reuse the source's own labeled fields where present (e.g. if the source has a "Hazards" field, keep that as a key fact), cleaned up for consistent phrasing, not reinterpreted.
- summary is 2-4 sentences of plain-language overview, faithful to the source.
- Respond with ONLY a JSON object matching this shape, no other text:
{"title": string, "summary": string, "key_facts": {string: string}, "tags": [string]}
"""


def _build_user_prompt(record: dict, extra_instructions: str = "") -> str:
    parts = [f"Source URL: {record.get('url')}", f"Page title: {record.get('title')}"]
    if record.get("labeled_fields"):
        parts.append("Labeled fields found on the page:\n" + json.dumps(record["labeled_fields"], indent=2))
    text = (record.get("text") or "")[:8000]  # keep prompts bounded on very long pages
    if text:
        parts.append("Extracted page text:\n" + text)
    if extra_instructions:
        parts.append("Additional instructions: " + extra_instructions)
    return "\n\n".join(parts)


def summarize_record(record: dict, model: str = DEFAULT_MODEL, extra_instructions: str = "", client=None) -> dict:
    """record is one line from content.jsonl (extract.build_content_record's shape).
    Returns a card dict: {source_url, model, generated_at, title, summary, key_facts, tags}.
    Raises RuntimeError if the optional [ai] dependency isn't installed."""
    if client is None:
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(f"Summarization requires the optional dependency. {_AI_EXTRA_HINT}") from e
        client = anthropic.Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(record, extra_instructions)}],
    )
    raw_text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")

    try:
        card = json.loads(raw_text)
    except json.JSONDecodeError:
        card = {"title": record.get("title"), "summary": raw_text.strip(), "key_facts": {}, "tags": []}

    return {
        "source_url": record.get("url"),
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": card.get("title"),
        "summary": card.get("summary"),
        "key_facts": card.get("key_facts", {}),
        "tags": card.get("tags", []),
    }
