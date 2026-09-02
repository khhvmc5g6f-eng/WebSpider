from webspider.sitemap import _parse_sitemap_xml

URLSET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/a</loc></url>
  <url><loc>https://example.com/b</loc></url>
</urlset>"""

INDEX_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap>
</sitemapindex>"""


def test_parse_urlset():
    urls, nested = _parse_sitemap_xml(URLSET_XML)
    assert urls == ["https://example.com/a", "https://example.com/b"]
    assert nested == []


def test_parse_sitemap_index():
    urls, nested = _parse_sitemap_xml(INDEX_XML)
    assert urls == []
    assert nested == ["https://example.com/sitemap-1.xml", "https://example.com/sitemap-2.xml"]


def test_parse_invalid_xml_returns_empty():
    urls, nested = _parse_sitemap_xml("not xml")
    assert urls == [] and nested == []
