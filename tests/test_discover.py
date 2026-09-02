from webspider.discover import find_image_urls, find_internal_links

HTML = """
<html><body>
<img src="/a.jpg">
<img data-src="/b.png" srcset="/b-small.png 480w, /b-large.png 1200w">
<picture><source srcset="/c-large.webp 800w, /c-small.webp 300w"></picture>
<meta property="og:image" content="/og.jpg">
<div style="background-image: url('/bg.jpg')"></div>
<a href="/page2">next</a>
<a href="https://other.example/x">external</a>
</body></html>
"""


def test_find_image_urls():
    urls = find_image_urls(HTML, "https://example.com/")
    assert "https://example.com/a.jpg" in urls
    assert "https://example.com/b-large.png" in urls
    assert "https://example.com/c-large.webp" in urls
    assert "https://example.com/og.jpg" in urls
    assert "https://example.com/bg.jpg" in urls


def test_find_internal_links_same_domain():
    links = find_internal_links(HTML, "https://example.com/", same_domain=True)
    assert links == ["https://example.com/page2"]


def test_find_internal_links_any_domain():
    links = find_internal_links(HTML, "https://example.com/", same_domain=False)
    assert "https://other.example/x" in links
