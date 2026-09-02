import json
from types import SimpleNamespace

import pytest

from webspider.humanize import (
    HumanizationIntegrityError,
    audit_text,
    compare_anchors,
    extract_anchors,
    humanize_text,
)


class _FakeMessages:
    def __init__(self, response_text):
        self.response_text = response_text
        self.last_call = None

    def create(self, **kwargs):
        self.last_call = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.response_text)])


class _FakeClient:
    def __init__(self, response_text):
        self.messages = _FakeMessages(response_text)


def test_extract_and_compare_anchors_preserves_counts():
    source = 'Email a@example.com twice. Budget £1,250, then £1,250. See "Keep this".'
    assert "a@example.com" in extract_anchors(source)
    report = compare_anchors(source, source)
    assert report["passed"] is True
    assert report["source_anchor_count"] == report["revised_anchor_count"]


def test_audit_is_explainable_and_not_an_ai_detector():
    report = audit_text("It is important to note that this is robust. Furthermore, it is seamless.")
    assert report["label"] == "editorial_quality"
    assert any(signal["code"] == "stock_phrasing" for signal in report["signals"])
    assert "not an AI detector" in report["disclaimer"]


def test_humanize_returns_audits_and_integrity_report():
    client = _FakeClient(json.dumps({"text": "The fee is £25 on 12 June 2026. See https://example.com."}))
    result = humanize_text(
        "On 12 June 2026, the fee is £25. See https://example.com.",
        profile="concise",
        client=client,
    )
    assert result["integrity"]["passed"] is True
    assert result["profile"] == "concise"
    assert result["before"]["label"] == "editorial_quality"
    assert "Never claim to bypass AI detectors" in client.messages.last_call["system"]


def test_humanize_fails_closed_when_numbers_change():
    client = _FakeClient('{"text": "The fee is £30."}')
    with pytest.raises(HumanizationIntegrityError) as exc:
        humanize_text("The fee is £25.", client=client)
    assert exc.value.report["passed"] is False
    assert "£25" in exc.value.report["missing"]


def test_humanize_rejects_non_json_response():
    with pytest.raises(RuntimeError, match="required JSON"):
        humanize_text("Keep 42 exactly.", client=_FakeClient("plain text"))
