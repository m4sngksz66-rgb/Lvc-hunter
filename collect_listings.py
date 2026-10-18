#!/usr/bin/env python3
"""Collect public listing pages into a manifest; no login, evasion, or search scraping.

Accepts URLs supplied in a UTF-8 text file. Downloads only image URLs from public
metadata (JSON-LD Product image, og:image, twitter:image). Respect site restrictions.
"""
import argparse
import hashlib
import json
import mimetypes
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

HOSTS = {'sellpy.se': 'sellpy', 'tradera.com': 'tradera', 'ebay.com': 'ebay', 'ebay.co.uk': 'ebay', 'ebay.de': 'ebay', 'ebay.se': 'ebay'}
HEADERS = {'User-Agent': 'LVC-Hunter/0.8 (public listing metadata; personal research)'}

def platform_of(url):
    host = (urlparse(url).hostname or '').lower()
    for suffix, name in HOSTS.items():
        if host == suffix or host.endswith('.' + suffix):
            return name
    raise ValueError('Unsupported listing domain: ' + host)

def http_url(url):
    p = urlparse(url)
    return p.scheme == 'https' and bool(p.hostname) and not p.username and not p.password

def flatten_images(value):
    if isinstance(value, str): return [value]
    if isinstance(value, list):
        result=[]
        for v in value: result.extend(flatten_images(v))
        return result
    if isinstance(value, dict): return flatten_images(value.get('url') or value.get('contentUrl') or '')
    return []

def extract_metadata(html, page_url):
    soup=BeautifulSoup(html,'html.parser')
    def meta(*names):
        for name in names:
            el=soup.find('meta',attrs={'property':name}) or soup.find('meta',attrs={'name':name})
            if el and el.get('content'): return el['content'].strip()
        return ''
    title=meta('og:title','twitter:title') or (soup.title.get_text(' ',strip=True) if soup.title else '')
    price=meta('product:price:amount','og:price:amount')
    images=[]
    for script in soup.find_all('script',type='application/ld+json'):
        try: obj=json.loads(script.string or script.get_text())
        except (ValueError,TypeError): continue
        stack=[obj]
        while stack:
            node=stack.pop()
            if isinstance(node,list): stack.extend(node);continue
            if not isinstance(node,dict):continue
            stack.extend(v for k,v in node.items() if k in ('@graph','mainEntity','itemListElement'))
            typ=node.get('@type',[])
            if isinstance(typ,str):typ=[typ]
            if any(str(t).lower().endswith('product') for t in typ):
                images.extend(flatten_images(node.get('image',[])))
                title=node.get('name') or title
                offers=node.get('offers',{})
                if isinstance(offers,list):offers=offers[0] if offers else {}
                if isinstance(offers,dict) and offers.get('price') is not None:
                    price=str(offers['price']) + (' '+str(offers.get('priceCurrency','')) if offers.get('priceCurrency') else '')
    images.extend([meta('og:image'),meta('twitter:image')])
    # Public HTML image elements are a fallback when metadata is absent.
    # Do not include decorative logos/icons or data URIs.
    if not images or not any(images):
        for tag in soup.find_all('img'):
            candidates=[tag.get('src'),tag.get('data-src'),tag.get('data-original')]
            srcset=tag.get('srcset') or tag.get('data-srcset') or ''
            if srcset:
                candidates.extend(part.strip().split(' ')[0] for part in srcset.split(','))
            for candidate in candidates:
                if candidate and not candidate.startswith(('data:', 'blob:')):
                    images.append(candidate)

    cleaned=[];seen=set()
    for candidate in images:
        if not candidate:continue
        u=urljoin(page_url,candidate)
        if http_url(u) and u not in seen:
            cleaned.append(u);seen.add(u)
    return {'title':str(title)[:300], 'price':str(price)[:100], 'image_urls':cleaned[:12]}

def download_image(session,url,dest,max_bytes=8_000_000):
    if not http_url(url):raise ValueError('Non-HTTPS image URL')
    with session.get(url,stream=True,timeout=18,allow_redirects=True) as r:
        r.raise_for_status()
        if not http_url(r.url):raise ValueError('Unsafe image redirect')
        ctype=r.headers.get('content-type','').split(';')[0].lower()
        if ctype not in ('image/jpeg','image/png','image/webp'):raise ValueError('Not an accepted image type: '+ctype)
        ext={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}[ctype]
        target=dest.with_suffix(ext);target.parent.mkdir(parents=True,exist_ok=True)
        count=0
        with target.open('wb') as f:
            for chunk in r.iter_content(65536):
                count+=len(chunk)
                if count>max_bytes:
                    f.close();target.unlink(missing_ok=True);raise ValueError('Image exceeds byte limit')
                f.write(chunk)
        if count<200:target.unlink(missing_ok=True);raise ValueError('Image too small')
        return str(target)

def collect(urls,output,photos,download=True,delay=1.5,session=None):
    session=session or requests.Session();session.headers.update(HEADERS)
    listings=[];errors=[];seen=set()
    for idx,url in enumerate(urls):
        url=url.strip()
        if not url or url.startswith('#'):continue
        try:
            if not http_url(url):raise ValueError('Only HTTPS URLs are supported')
            platform=platform_of(url)
            if url in seen:continue
            seen.add(url)
            response=session.get(url,timeout=20)
            response.raise_for_status()
            if platform_of(response.url)!=platform:raise ValueError('Redirected outside original marketplace')
            data=extract_metadata(response.text,response.url)
            if not data['image_urls']:
                # Empty extraction must not silently count as success.
                html=response.text
                soup=BeautifulSoup(html,'html.parser')
                page_title=soup.title.get_text(' ',strip=True)[:120] if soup.title else ''
                errors.append({'url':url,'error':'No public image URLs found in HTML',
                               'http_status':response.status_code,
                               'content_type':response.headers.get('content-type','')[:100],
                               'html_bytes':len(response.content),
                               'page_title':page_title,
                               'script_count':len(soup.find_all('script'))})
            images=[]
            if download:
                for j,img in enumerate(data['image_urls']):
                    try:
                        name=hashlib.sha256((url+'|'+img).encode()).hexdigest()[:18]
                        images.append(download_image(session,img,photos/name))
                    except (requests.RequestException,ValueError,OSError) as e:
                        errors.append({'url':url,'image':img,'error':str(e)[:180]})
            listings.append({'platform':platform,'url':response.url,'title':data['title'],'price':data['price'],'images':images,'image_urls':data['image_urls']})
        except (requests.RequestException,ValueError,OSError) as e:
            errors.append({'url':url,'error':str(e)[:180]})
        if delay and idx<len(urls)-1:time.sleep(delay)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(listings,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'listings':len(listings),'downloaded_images':sum(len(x['images']) for x in listings),'errors':errors}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('urls',help='Text file with one public listing URL per line')
    ap.add_argument('--out',default='results/collected.json')
    ap.add_argument('--photos',default='photos')
    ap.add_argument('--metadata-only',action='store_true',help='Do not download images')
    ap.add_argument('--delay',type=float,default=1.5)
    args=ap.parse_args()
    if args.delay<0:ap.error('--delay must be >= 0')
    result=collect(Path(args.urls).read_text(encoding='utf-8').splitlines(),Path(args.out),Path(args.photos),not args.metadata_only,args.delay)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
