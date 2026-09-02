import json

from webspider.inspect import extract_embedded_state, find_urls_in_data

NEXT_HTML = """
<html><body>
<script id="__NEXT_DATA__" type="application/json">
{"props": {"pageProps": {"site": {"name": "Some Hill", "images": ["/media/hill1.jpg", "https://cdn.example.com/hill2.png"], "source": "https://official-registry.example.com/sites/123"}}}}
</script>
</body></html>
"""

GENERIC_STATE_HTML = """
<html><body><script>
window.__INITIAL_STATE__ = {"user": {"name": "test"}, "nested": {"a": [1, 2, {"b": "c"}]}};
console.log("after");
</script></body></html>
"""

MALFORMED_NUXT_HTML = """
<html><body><script>
window.__NUXT__=(function(a,b){return {data:[a,b]}}("x","y"));
</script></body></html>
"""


def test_extract_next_data():
    state = extract_embedded_state(NEXT_HTML)
    assert "__NEXT_DATA__" in state
    assert state["__NEXT_DATA__"]["props"]["pageProps"]["site"]["name"] == "Some Hill"


def test_extract_generic_window_state():
    state = extract_embedded_state(GENERIC_STATE_HTML)
    assert state["__INITIAL_STATE__"]["nested"]["a"] == [1, 2, {"b": "c"}]


def test_malformed_nuxt_iife_skipped_not_crashed():
    # Not valid JSON (function call with variable substitution) — should be
    # skipped gracefully, not raise or produce garbage.
    state = extract_embedded_state(MALFORMED_NUXT_HTML)
    assert "__NUXT__" not in state


def test_find_urls_in_data_splits_images_and_links_and_resolves_relative():
    state = extract_embedded_state(NEXT_HTML)
    found = find_urls_in_data(state["__NEXT_DATA__"], base_url="https://example.com/sites/some-hill")
    assert "https://example.com/media/hill1.jpg" in found["images"]
    assert "https://cdn.example.com/hill2.png" in found["images"]
    assert "https://official-registry.example.com/sites/123" in found["links"]


def test_find_urls_in_data_empty_for_no_data():
    assert find_urls_in_data({}, "https://example.com/") == {"images": [], "links": []}
    assert find_urls_in_data(None, "https://example.com/") == {"images": [], "links": []}
