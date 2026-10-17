import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from collect_listings import collect

class MockResponse:
    def __init__(self,text='',body=b'',ctype='text/html',url='https://www.tradera.com/item/123'):
        self.text=text;self.body=body;self.url=url;self.headers={'content-type':ctype}
    def raise_for_status(self):pass
    def iter_content(self,n):yield self.body
    def __enter__(self):return self
    def __exit__(self,*args):pass
class MockSession:
    def __init__(self,body):self.headers={};self.body=body
    def get(self,url,**kwargs):
        if 'images.example' in url:return MockResponse(body=self.body,ctype='image/jpeg',url=url)
        return MockResponse('<html><meta property="og:title" content="Test jeans"><meta property="og:image" content="https://images.example/pair.jpg"></html>')

class IntegrationTests(unittest.TestCase):
    def test_collect_rank_report(self):
        with tempfile.TemporaryDirectory() as temp:
            tmp=Path(temp);b=io.BytesIO();Image.new('RGB',(96,96),(55,67,110)).save(b,format='JPEG')
            outcome=collect(['https://www.tradera.com/item/123'],tmp/'collected.json',tmp/'photos',session=MockSession(b.getvalue()),delay=0)
            self.assertEqual(outcome['downloaded_images'],1)
            subprocess.run([sys.executable,str(ROOT/'marketplace.py'),str(tmp/'collected.json'),'--model',str(ROOT/'models/lvc_model_v06.joblib'),'--out',str(tmp/'ranked.csv')],check=True,capture_output=True,text=True)
            subprocess.run([sys.executable,str(ROOT/'report_html.py'),str(tmp/'ranked.csv'),'--out',str(tmp/'report.html')],check=True,capture_output=True,text=True)
            with (tmp/'ranked.csv').open(newline='',encoding='utf-8') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),1)
            self.assertIn('Test jeans',(tmp/'report.html').read_text())
if __name__=='__main__':unittest.main()
