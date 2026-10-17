"""Audit public sale evidence. Do not silently turn asking prices into sold prices."""
import argparse,csv,json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
FIELDS={'platform','listing_id','title','status','displayed_price','currency','actual_paid_verified','model_key','tier','tier_verified','sold_date','source_url','notes'}
def audit(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    issues=[]; eligible=[]; seen=set()
    for i,row in enumerate(rows,2):
        if not FIELDS.issubset(row):raise ValueError('Missing columns: '+', '.join(sorted(FIELDS-set(row))))
        key=(row['platform'],row['listing_id'])
        if key in seen:issues.append(f'row {i}: duplicate listing')
        seen.add(key)
        try: amount=float(row['displayed_price'])
        except ValueError:amount=-1
        if amount<=0:issues.append(f'row {i}: invalid price')
        if urlparse(row['source_url']).scheme!='https':issues.append(f'row {i}: invalid source URL')
        if row['status'] not in {'sold','sold_price_uncertain','unsold'}:issues.append(f'row {i}: invalid status')
        if row['actual_paid_verified'] not in {'yes','no'}:issues.append(f'row {i}: invalid paid flag')
        if row['currency'] not in {'SEK','USD','EUR','GBP','JPY','NOK','DKK'}:issues.append(f'row {i}: unsupported currency')
        if row['status']=='sold' and row['actual_paid_verified']=='yes' and row['currency']=='SEK' and row['tier_verified']=='yes' and amount>0:
            eligible.append(row)
    return {'records':len(rows),'verified_SEK_tier_comparables':len(eligible),'by_status':dict(Counter(r['status'] for r in rows)),'issues':issues}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('path',nargs='?',default='data/sold_evidence.csv');a=ap.parse_args();print(json.dumps(audit(a.path),indent=2,ensure_ascii=False))
