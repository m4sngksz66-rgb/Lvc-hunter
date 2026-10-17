import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from collect_listings import extract_metadata,platform_of,http_url

class CollectTests(unittest.TestCase):
    def test_platforms(self):
        self.assertEqual(platform_of('https://www.sellpy.se/item/1'),'sellpy')
        self.assertEqual(platform_of('https://www.tradera.com/item/1'),'tradera')
        self.assertEqual(platform_of('https://www.ebay.com/itm/1'),'ebay')
        with self.assertRaises(ValueError):platform_of('https://sellpy.se.evil.test/x')
    def test_reject_http(self):
        self.assertFalse(http_url('http://www.sellpy.se/item/1'))
    def test_jsonld(self):
        page='''<html><head><meta property="og:image" content="/fallback.jpg"><script type="application/ld+json">{"@type":"Product","name":"Vintage jeans","image":["https://img.example.org/a.jpg","https://img.example.org/b.jpg"],"offers":{"price":"300","priceCurrency":"SEK"}}</script></head></html>'''
        m=extract_metadata(page,'https://www.tradera.com/item/1')
        self.assertEqual(m['title'],'Vintage jeans')
        self.assertEqual(m['price'],'300 SEK')
        self.assertEqual(len(m['image_urls']),3)
    def test_malformed_jsonld_fallback(self):
        m=extract_metadata('<title>Example</title><script type="application/ld+json">{bad</script><meta property="og:image" content="https://x.org/1.jpg">','https://www.sellpy.se/item/1')
        self.assertEqual(m['title'],'Example')
        self.assertEqual(len(m['image_urls']),1)
if __name__=='__main__':unittest.main()
