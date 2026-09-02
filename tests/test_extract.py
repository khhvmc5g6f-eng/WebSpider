import pytest

from webspider.extract import extract_labeled_fields

DL_HTML = """
<html><body>
<dl>
  <dt>Hazards</dt><dd>Power lines to the north, rotor behind the ridge</dd>
  <dt>Wind window</dt><dd>SW 210-260 degrees</dd>
</dl>
</body></html>
"""

TABLE_HTML = """
<html><body>
<table>
  <tr><th>Hazards</th><td>Loose rock on final approach</td></tr>
  <tr><td><strong>Wind window</strong></td><td>N 320-020 degrees</td></tr>
  <tr><td>Not a label</td><td>Second col</td><td>Third col</td></tr>
</table>
</body></html>
"""

INLINE_HTML = """
<html><body>
<p><strong>Hazards:</strong> A single power line crosses the LZ.</p>
<li><strong>Wind window:</strong> Best from the SW, avoid north winds.</li>
<p>No label here, just prose.</p>
</body></html>
"""


def test_labeled_fields_from_definition_list():
    fields = extract_labeled_fields(DL_HTML)
    assert fields["Hazards"] == "Power lines to the north, rotor behind the ridge"
    assert fields["Wind window"] == "SW 210-260 degrees"


def test_labeled_fields_from_table():
    fields = extract_labeled_fields(TABLE_HTML)
    assert fields["Hazards"] == "Loose rock on final approach"
    assert fields["Wind window"] == "N 320-020 degrees"
    assert "Not a label" not in fields  # 3-cell row is skipped, not a label/value pair


def test_labeled_fields_from_inline_bold():
    fields = extract_labeled_fields(INLINE_HTML)
    assert fields["Hazards"] == "A single power line crosses the LZ."
    assert fields["Wind window"] == "Best from the SW, avoid north winds."


def test_labeled_fields_empty_html():
    assert extract_labeled_fields("") == {}
    assert extract_labeled_fields(None) == {}


def test_extract_page_requires_optional_dependency_or_works():
    trafilatura = pytest.importorskip("trafilatura")
    from webspider.extract import extract_page

    html = "<html><body><article><h1>Title</h1><p>Some real article body text here for extraction.</p></article></body></html>"
    result = extract_page(html, "https://example.com/article")
    assert result["title"]
    assert "article body text" in (result["text"] or "")


def test_extract_structured_data_finds_jsonld():
    pytest.importorskip("extruct")
    from webspider.extract import extract_structured_data

    html = """<html><body><script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "Article", "headline": "Test"}
    </script></body></html>"""
    data = extract_structured_data(html, "https://example.com/")
    assert len(data["json-ld"]) == 1
    assert data["json-ld"][0]["headline"] == "Test"
