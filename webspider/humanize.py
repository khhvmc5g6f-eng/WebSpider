"""Source-faithful writing revision and deterministic quality diagnostics.

This module improves rhythm, clarity, and voice. It does not estimate whether
text was written by AI and makes no claim about detector outcomes.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone

DEFAULT_MODEL = "claude-sonnet-5"
PROFILES = ("plain", "professional", "editorial", "concise")

_AI_EXTRA_HINT = "Install with: pip install 'webspider[ai]', and set ANTHROPIC_API_KEY."
_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
_WORD_PATTERN = re.compile(r"\b[\w'-]+\b")
_ANCHOR_PATTERNS = (
    re.compile(r"https?://[^\s<>()\]\[{}]+", re.I),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
    re.compile(
        r"(?<!\w)(?:£|\$|€)?\d+(?:[,.]\d+)*(?:\s?(?:%|°[CF]?|mg|g|kg|ml|l|cm|mm|km|m|mph|kph|hours?|hrs?|minutes?|mins?|seconds?|secs?))?(?!\w)",
        re.I,
    ),
    re.compile(r"[\"“]([^\"”\n]{2,})[\"”]"),
)
_STOCK_PHRASES = (
    "in conclusion",
    "it is important to note",
    "it is worth noting",
    "in today's world",
    "ever-evolving landscape",
    "delve into",
    "a testament to",
    "plays a crucial role",
    "furthermore",
    "moreover",
    "seamless",
    "robust",
)


class HumanizationIntegrityError(RuntimeError):
    """Raised when a revision changes source-locked anchors."""

    def __init__(self, report: dict):
        self.report = report
        details = []
        if report["missing"]:
            details.append("missing: " + ", ".join(report["missing"]))
        if report["added"]:
            details.append("added: " + ", ".join(report["added"]))
        super().__init__("Revision failed source-integrity checks (" + "; ".join(details) + ")")


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_PATTERN.split(text.strip()) if part.strip()]


def extract_anchors(text: str) -> list[str]:
    """Extract exact values that a style-only revision must not change."""
    matches = []
    for pattern in _ANCHOR_PATTERNS:
        for match in pattern.finditer(text or ""):
            value = match.group(0).rstrip(".,;:")
            if value:
                matches.append(value)
    return matches


def compare_anchors(source: str, revised: str) -> dict:
    """Compare immutable values, including repeated occurrences."""
    source_counts = Counter(extract_anchors(source))
    revised_counts = Counter(extract_anchors(revised))
    missing = list((source_counts - revised_counts).elements())
    added = list((revised_counts - source_counts).elements())
    return {
        "passed": not missing and not added,
        "missing": sorted(missing),
        "added": sorted(added),
        "source_anchor_count": sum(source_counts.values()),
        "revised_anchor_count": sum(revised_counts.values()),
    }


def audit_text(text: str) -> dict:
    """Return explainable editorial signals, not an AI-authorship score."""
    sentences = _sentences(text)
    lengths = [len(_WORD_PATTERN.findall(sentence)) for sentence in sentences]
    lowered = text.lower()
    signals = []

    found_stock = [phrase for phrase in _STOCK_PHRASES if phrase in lowered]
    if found_stock:
        signals.append({
            "code": "stock_phrasing",
            "message": "Stock phrasing may make the prose feel generic.",
            "examples": found_stock,
        })

    long_count = sum(length > 34 for length in lengths)
    if long_count:
        signals.append({
            "code": "long_sentences",
            "message": f"{long_count} sentence(s) exceed 34 words.",
        })

    if len(lengths) >= 4 and max(lengths) - min(lengths) <= 5:
        signals.append({
            "code": "uniform_rhythm",
            "message": "Sentence lengths are unusually uniform; vary rhythm where it helps clarity.",
        })

    openings = []
    for sentence in sentences:
        words = _WORD_PATTERN.findall(sentence.lower())[:2]
        if words:
            openings.append(" ".join(words))
    repeated = sorted(opening for opening, count in Counter(openings).items() if count >= 3)
    if repeated:
        signals.append({
            "code": "repeated_openings",
            "message": "Several sentences begin the same way.",
            "examples": repeated,
        })

    score = max(0, 100 - sum(18 if s["code"] == "stock_phrasing" else 12 for s in signals))
    return {
        "score": score,
        "label": "editorial_quality",
        "signals": signals,
        "sentence_count": len(sentences),
        "average_sentence_words": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "disclaimer": "This is a writing-quality diagnostic, not an AI detector or authorship judgement.",
    }


def _build_prompt(text: str, profile: str, voice_sample: str = "") -> str:
    profile_notes = {
        "plain": "direct, clear, unforced language",
        "professional": "confident professional language without corporate filler",
        "editorial": "polished editorial prose with purposeful rhythm",
        "concise": "the shortest complete version that preserves every material point",
    }
    voice = ""
    if voice_sample.strip():
        voice = (
            "\n\nVOICE SAMPLE\nUse only its broad cadence, formality, and vocabulary level. "
            "Do not copy its facts or distinctive phrases.\n" + voice_sample.strip()[:4000]
        )
    return f"""Revise the SOURCE TEXT into {profile_notes[profile]}.

This is an editorial revision, not a factual rewrite.
- Preserve the exact meaning and all material detail.
- Preserve every number, date, measurement, URL, email address, and quotation exactly.
- Do not add facts, examples, claims, citations, uncertainty, or conclusions.
- Prefer concrete subjects and verbs. Remove stock transitions and generic filler.
- Vary sentence length only where it improves clarity. Do not manufacture quirks, errors, slang, or anecdotes.
- Keep specialist terms that carry meaning. Do not force synonyms.
- Return ONLY JSON in this form: {{"text": "revised text"}}.

SOURCE TEXT
{text.strip()[:16000]}{voice}"""


def humanize_text(
    text: str,
    profile: str = "plain",
    voice_sample: str = "",
    model: str = DEFAULT_MODEL,
    client=None,
) -> dict:
    """Revise text and fail closed if exact-value anchors drift."""
    if not text or not text.strip():
        raise ValueError("Text is required.")
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile: {profile}. Choose one of: {', '.join(PROFILES)}")
    if client is None:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(f"Humanisation requires the optional dependency. {_AI_EXTRA_HINT}") from exc
        client = anthropic.Anthropic()

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=(
            "You are a careful editor. Improve naturalness and clarity without changing facts. "
            "Never claim to bypass AI detectors or disguise authorship."
        ),
        messages=[{"role": "user", "content": _build_prompt(text, profile, voice_sample)}],
    )
    raw = "".join(block.text for block in response.content if getattr(block, "type", None) == "text").strip()
    try:
        revised = json.loads(raw)["text"].strip()
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        raise RuntimeError("The model did not return the required JSON response.") from exc

    integrity = compare_anchors(text, revised)
    if not integrity["passed"]:
        raise HumanizationIntegrityError(integrity)

    return {
        "text": revised,
        "profile": profile,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "integrity": integrity,
        "before": audit_text(text),
        "after": audit_text(revised),
        "provenance": "AI-assisted editorial revision; source-integrity checks passed.",
    }
