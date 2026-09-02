from webspider.discover import find_image_urls, find_internal_links

GRAPH_HTML = """
<html><body>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "Product", "image": "/graph1.jpg"},
  {"@type": "ImageObject", "url": "/graph2.jpg"}
]}
</script>
</body></html>
"""


def _urls(candidates):
    return {c.url for c in candidates}


def test_jsonld_at_graph_images_found():
    urls = _urls(find_image_urls(GRAPH_HTML, "https://example.com/"))
    assert "https://example.com/graph1.jpg" in urls
    assert "https://example.com/graph2.jpg" in urls


def test_srcset_density_descriptor_picks_higher_density_regardless_of_order():
    html_ordered = '<img srcset="a.jpg 1x, b.jpg 2x">'
    html_reversed = '<img srcset="b.jpg 2x, a.jpg 1x">'
    assert _urls(find_image_urls(html_ordered, "https://example.com/")) == {"https://example.com/b.jpg"}
    assert _urls(find_image_urls(html_reversed, "https://example.com/")) == {"https://example.com/b.jpg"}


def test_javascript_scheme_filtered_out():
    html = '<div style="background-image:url(javascript:alert(1))"></div>'
    assert find_image_urls(html, "https://example.com/") == []


def test_none_html_does_not_crash():
    assert find_image_urls(None, "https://example.com/") == []
    assert find_internal_links(None, "https://example.com/") == []


def test_empty_html_does_not_crash():
    assert find_image_urls("", "https://example.com/") == []
