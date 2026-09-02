import json
from types import SimpleNamespace

from webspider.summarize import summarize_record, _build_user_prompt


class _FakeMessages:
    def __init__(self, response_text):
        self._response_text = response_text
        self.last_call = None

    def create(self, **kwargs):
        self.last_call = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._response_text)])


class _FakeClient:
    def __init__(self, response_text):
        self.messages = _FakeMessages(response_text)


RECORD = {
    "url": "https://example.com/site-guide/some-hill",
    "title": "Some Hill Flying Site",
    "text": "Some Hill is a popular soaring site. Best flown in southwesterly winds.",
    "labeled_fields": {"Hazards": "Power lines near the LZ", "Wind window": "SW 210-260 degrees"},
}


def test_prompt_includes_labeled_fields_and_text():
    prompt = _build_user_prompt(RECORD)
    assert "Power lines near the LZ" in prompt
    assert "Some Hill is a popular soaring site" in prompt
    assert RECORD["url"] in prompt


def test_summarize_record_parses_valid_json_response():
    card_json = json.dumps({
        "title": "Some Hill Flying Site",
        "summary": "A soaring site best flown in SW winds, with power lines near the LZ.",
        "key_facts": {"Hazards": "Power lines near the LZ", "Wind window": "SW 210-260 degrees"},
        "tags": ["soaring", "sw-facing"],
    })
    client = _FakeClient(card_json)
    result = summarize_record(RECORD, client=client)

    assert result["source_url"] == RECORD["url"]
    assert result["title"] == "Some Hill Flying Site"
    assert result["key_facts"]["Hazards"] == "Power lines near the LZ"
    assert "generated_at" in result
    assert "model" in result


def test_summarize_record_falls_back_gracefully_on_non_json_response():
    client = _FakeClient("This is not JSON at all.")
    result = summarize_record(RECORD, client=client)
    assert result["summary"] == "This is not JSON at all."
    assert result["key_facts"] == {}


def test_summarize_record_sends_system_prompt_forbidding_invention():
    client = _FakeClient('{"title": "x", "summary": "y", "key_facts": {}, "tags": []}')
    summarize_record(RECORD, client=client)
    assert "never invent" in client.messages.last_call["system"].lower()
