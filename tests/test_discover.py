from webspider.discover import find_image_urls, find_internal_links

HTML = """
<html><body>
<img src="/a.jpg" alt="A cat">
<img data-src="/b.png" srcset="/b-small.png 480w, /b-large.png 1200w">
<picture><source srcset="/c-large.webp 800w, /c-small.webp 300w"></picture>
<meta property="og:image" content="/og.jpg">
<div style="background-image: url('/bg.jpg')"></div>
<div class="gallery"><img src="/gallery1.jpg"></div>
<a href="/page2">next</a>
<a href="https://other.example/x">external</a>
<script type="application/ld+json">
{"@type": "Product", "image": ["/jsonld1.jpg", {"@type": "ImageObject", "url": "/jsonld2.jpg"}]}
</script>
</body></html>
"""


def _urls(candidates):
    return {c.url for c in candidates}


def test_find_image_urls():
    urls = _urls(find_image_urls(HTML, "https://example.com/"))
    assert "https://example.com/a.jpg" in urls
    assert "https://example.com/b-large.png" in urls
    assert "https://example.com/c-large.webp" in urls
    assert "https://example.com/og.jpg" in urls
    assert "https://example.com/bg.jpg" in urls


def test_alt_text_captured():
    candidates = find_image_urls(HTML, "https://example.com/")
    by_url = {c.url: c.alt for c in candidates}
    assert by_url["https://example.com/a.jpg"] == "A cat"


def test_jsonld_images_found():
    urls = _urls(find_image_urls(HTML, "https://example.com/"))
    assert "https://example.com/jsonld1.jpg" in urls
    assert "https://example.com/jsonld2.jpg" in urls


def test_selector_scopes_to_gallery_only():
    urls = _urls(find_image_urls(HTML, "https://example.com/", scope_selector=".gallery"))
    assert urls == {"https://example.com/gallery1.jpg"}


def test_find_internal_links_same_domain():
    links = find_internal_links(HTML, "https://example.com/", same_domain=True)
    assert links == ["https://example.com/page2"]


def test_find_internal_links_any_domain():
    links = find_internal_links(HTML, "https://example.com/", same_domain=False)
    assert "https://other.example/x" in links
