#!/usr/bin/env python3
"""Marketplace listing importer and offline ranking. Uses user-provided listing JSON; no scraping claims."""
import argparse,csv,json,hashlib,sys
from pathlib import Path
from urllib.parse import urlparse
import joblib,numpy as np
from lvc_hunter import image_features
from price_control import classify_listing, assess_deal, load_comparables, PRIORITY
from condition_signals import analyze_condition, valencia_unwashed_priority
from review_policy import decide
from evidence_checklist import checklist

def main():
 ap=argparse.ArgumentParser(description='Rank marketplace listings from a JSON manifest and local downloaded listing photos')
 ap.add_argument('manifest',help='JSON list: {platform,url,title,price,images:[local file paths]}')
 ap.add_argument('--model',default='models/lvc_model_v06.joblib');ap.add_argument('--out',default='results/listings.csv');ap.add_argument('--threshold',type=float,default=.25)
 ap.add_argument('--comparables',default='data/sold_comparables.csv');ap.add_argument('--min-comparables',type=int,default=3);ap.add_argument('--min-discount',type=float,default=0.30);ap.add_argument('--show-unpriced',action='store_true',help='Include interesting listings without proven price discount in review')
 a=ap.parse_args(); comparables=load_comparables(a.comparables); listings=json.loads(Path(a.manifest).read_text(encoding='utf-8'))
 if not isinstance(listings,list):raise ValueError('Manifest must be a JSON list')
 model=joblib.load(a.model)['model'];rows=[];bad=[]
 for n,item in enumerate(listings):
  url=item.get('url','');host=urlparse(url).hostname or ''
  platform=(item.get('platform') or host).lower()
  if not url.startswith(('https://','http://')):bad.append(f'listing {n}: invalid URL');continue
  scores=[]
  for img in item.get('images',[]):
   path=Path(img)
   if not path.is_file():bad.append(f'listing {n}: missing image {img}');continue
   try:
    x=image_features(path).reshape(1,-1)
    scores.append(float(model.predict_proba(x)[0,1]))
   except Exception as e:bad.append(f'listing {n}: {path}: {e}')
  if not scores:bad.append(f'listing {n}: no usable images');continue
  # High recall: best single photo can surface an item; also report average for transparency.
  peak=max(scores);mean=float(np.mean(scores));score=.8*peak+.2*mean
  tier,confidence=classify_listing(item.get('title',''),item.get('description',''),item.get('verified_tier'))
  condition=analyze_condition(item.get('title',''),item.get('description',''),item.get('verified_condition'))
  # Premium conditions must never be valued using ordinary worn examples.
  matching_comparables=[c for c in comparables if (c.get('condition','').strip().lower()==condition['condition'])] if condition['condition'] in ('nos','nwt','nwot','unwashed') else [c for c in comparables if c.get('condition','').strip().lower() in ('','used','unknown')]
  # Seller expertise is a weak heuristic, not a price adjustment or proof of no bargain.
  deal=assess_deal(item.get('price',''),tier,matching_comparables,item.get('shipping_sek',0),a.min_comparables,a.min_discount,item.get('model_key',''))
  special=valencia_unwashed_priority(tier,confidence,condition)
  lane,reasons=decide(score,a.threshold,confidence,condition,deal,item.get('model_key',''),item.get('shipping_sek') is not None)
  review=int(lane=='bargain_alert' or (a.show_unpriced and lane=='manual_review'))
  rows.append({'tier':tier,'tier_confidence':confidence,'priority':PRIORITY[tier],**condition,'valencia_unwashed':special,**deal,'platform':platform,'url':url,'title':item.get('title',''),'price':item.get('price',''),'score':round(score,4),'best_image_score':round(peak,4),'mean_image_score':round(mean,4),'images_scored':len(scores),'review':review,'review_lane':lane,'review_reasons':';'.join(reasons),'needed_evidence':' | '.join(checklist(item.get('title',''),item.get('description',''),tier,condition['condition'],confidence,condition['condition_evidence']))})
 rows.sort(key=lambda r:(-r['review'],r['priority'],-(r['discount_pct'] if isinstance(r['discount_pct'],float) else -999),-r['score']))
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=['platform','url','title','price','tier','tier_confidence','priority','condition','condition_evidence','condition_signals','seller_knowledge','valencia_unwashed','total_sek','reference_sek','discount_pct','comparables_used','deal_status','score','best_image_score','mean_image_score','images_scored','review','review_lane','review_reasons','needed_evidence']);writer.writeheader();writer.writerows([{**r,'condition_signals':';'.join(r['condition_signals'])} for r in rows])
 print(json.dumps({'ranked_listings':len(rows),'flagged_for_review':sum(r['review'] for r in rows),'errors':bad,'output':str(out)},ensure_ascii=False,indent=2))
 if bad:sys.exit(2)
if __name__=='__main__':main()
