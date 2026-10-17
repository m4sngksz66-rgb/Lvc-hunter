"""Evidence-based deal assessment. No invented market prices, no automatic currency conversion."""
import csv
import re
import statistics
from datetime import date
from pathlib import Path

TIERS = ('true_vintage','lvc_valencia_555','japanese_selvedge_repro','lvc_non_usa','unclassified')
LABELS = {'true_vintage':'Äkta äldre vintage','lvc_valencia_555':'LVC Valencia Street (555)','japanese_selvedge_repro':'Japansk selvedge/reproduktion','lvc_non_usa':'Senare LVC utanför USA','unclassified':'Ej säkert identifierad'}
PRIORITY = {'true_vintage':1,'lvc_valencia_555':2,'japanese_selvedge_repro':3,'lvc_non_usa':4,'unclassified':5}

def classify_listing(title='',description='',verified_tier=None):
    if verified_tier in TIERS and verified_tier != 'unclassified':return verified_tier,'verified'
    s=(title+' '+description).lower()
    # Text clues alone are weak. The 555 factory code must be specifically linked to the button/factory.
    if re.search(r'\b(valencia(?: street)?|factory\s*555|button\s*(?:stamp|code)?\s*555|knapp(?:kod|stämpel)?\s*555)\b',s) and re.search(r'\b(lvc|levi.?s vintage clothing|501xx|501zxx)\b',s):
        return 'lvc_valencia_555','text_clue'
    if re.search(r'\b(levi.?s japan|levis japan|made in japan|japan(?:ese)? selvedge|japan(?:ese)? repro|warehouse|sugar cane|fullcount|evisu|momotaro|oni denim|samurai jeans|the flat head)\b',s):
        return 'japanese_selvedge_repro','text_clue'
    if re.search(r'\b(lvc|levi.?s vintage clothing)\b',s) and re.search(r'\b(made in (?:turkey|türkiye|bulgaria|china|mexico|portugal)|tillverkad i (?:turkiet|bulgarien|kina|mexiko|portugal))\b',s):
        return 'lvc_non_usa','text_clue'
    # 'Vintage', 'Big E', '501XX' are not proof of authentic age.
    return 'unclassified','unverified'

def parse_sek_price(value):
    if isinstance(value,(int,float)) and not isinstance(value,bool):return float(value) if value>=0 else None
    s=str(value or '').strip().lower().replace('\u00a0',' ').replace('\u202f',' ')
    if not s:return None
    if re.search(r'\b(?:usd|eur|gbp|dkk|nok|jpy|dollar|euro)\b|[$€£¥]',s):return None
    if not (re.search(r'\b(?:sek|kr|kronor)\b',s) or re.fullmatch(r'[\d\s.,]+',s)):return None
    s=re.sub(r'\b(?:sek|kr|kronor)\b','',s).strip().replace(' ','')
    if not re.fullmatch(r'\d[\d.,]*',s):return None
    if ',' in s and '.' in s:
        if s.rfind(',')>s.rfind('.'):s=s.replace('.','').replace(',','.')
        else:s=s.replace(',','')
    elif ',' in s:
        parts=s.split(',');s=s.replace(',','.') if len(parts)==2 and len(parts[1])<=2 else s.replace(',','')
    elif '.' in s:
        parts=s.split('.');s=s if len(parts)==2 and len(parts[1])<=2 else s.replace('.','')
    try:return float(s)
    except ValueError:return None

def load_comparables(path):
    if not path or not Path(path).is_file():return []
    with open(path,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def assess_deal(price,tier,comparables,shipping_sek=0,minimum=3,discount=0.30,model_key=''):
    """Use *sold* comparable prices only. Match exact model_key when provided; else tier-level.

    Tier-wide medians are indicative only; require ≥minimum sold examples.
    """
    price_sek=parse_sek_price(price)
    if price_sek is None:return {'deal_status':'unknown_price','reference_sek':'','discount_pct':'','comparables_used':0,'total_sek':''}
    total=price_sek+max(0,float(shipping_sek or 0))
    if tier not in TIERS or tier=='unclassified':return {'deal_status':'unverified_category','reference_sek':'','discount_pct':'','comparables_used':0,'total_sek':round(total,2)}
    matched=[]
    for row in comparables:
        if row.get('tier','').strip()!=tier or row.get('status','').strip().lower()!='sold':continue
        if model_key and row.get('model_key','').strip().lower()!=model_key.strip().lower():continue
        val=parse_sek_price(row.get('sold_price_sek',''))
        if val is not None and val>0:matched.append(val)
    if len(matched)<minimum:return {'deal_status':'insufficient_comparables','reference_sek':'','discount_pct':'','comparables_used':len(matched),'total_sek':round(total,2)}
    median=statistics.median(matched)
    pct=(median-total)/median
    return {'deal_status':'potential_bargain' if pct>=discount else 'not_a_bargain','reference_sek':round(median,2),'discount_pct':round(100*pct,1),'comparables_used':len(matched),'total_sek':round(total,2)}
