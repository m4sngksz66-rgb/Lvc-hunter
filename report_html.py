#!/usr/bin/env python3
"""Convert ranked listings CSV into a mobile-friendly, self-contained HTML review page."""
import argparse,csv,html
from pathlib import Path
from urllib.parse import urlparse

def main():
 p=argparse.ArgumentParser();p.add_argument('csv_file');p.add_argument('--out',default='results/fyndlista.html');a=p.parse_args()
 with open(a.csv_file,encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
 cards=[]
 for r in rows:
  url=r.get('url','');safe=url if urlparse(url).scheme in ('http','https') else '#'
  score=float(r['score']);status=r.get('deal_status','');discount=r.get('discount_pct','');reference=r.get('reference_sek','');tier=r.get('tier','');price_note=('Pris under jämförelsemedian (inte automatiskt verifierat fynd): '+discount+' % under median av '+r.get('comparables_used','')+' sålda jämförelser (median '+reference+' kr)') if status=='potential_bargain' else ('Ej fynd enligt jämförelserna' if status=='not_a_bargain' else 'Prisvärde okänt – inga säkra slutsatser');evidence=r.get('needed_evidence',''); lane=r.get('review_lane','manual_review');cards.append(f'''<article><div class="top"><strong>{html.escape(r.get('title',''))}</strong><span>{score:.0%}</span></div><p>{html.escape(r.get('platform',''))} · {html.escape(r.get('price',''))} · {r.get('images_scored','')} bilder</p><p><b>{html.escape(tier)}</b> · {html.escape(price_note)}</p><p><b>{'Verifierad fyndnotis' if lane=='bargain_alert' else 'Manuell granskning' if lane=='manual_review' else 'Ej prioriterad'}</b></p><p><small>Kontrollera: {html.escape(evidence)}</small></p><a href="{html.escape(safe,quote=True)}" target="_blank" rel="noopener noreferrer">Öppna annons ↗</a></article>''')
 document='''<!doctype html><html lang="sv"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LVC Hunter – fyndlista</title><style>body{font-family:system-ui,sans-serif;max-width:750px;margin:auto;padding:20px;background:#f5f4f1;color:#222}article{background:white;border:1px solid #ddd;border-radius:14px;padding:18px;margin:12px 0}.top{display:flex;justify-content:space-between;gap:15px}.top span{font-weight:800}a{color:#174f8a}p{color:#555;font-size:.92rem}</style><h1>LVC Hunter – fyndlista</h1><p>Modellpoäng är inte sannolikheten att annonsen är ett fynd. Priskontroll kräver minst tre faktiskt sålda jämförelser; verifiera modell, skick, storlek och äkthet.</p>'''+''.join(cards)+'</html>'
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(document,encoding='utf-8');print(f'Wrote {len(rows)} listings to {out}')
if __name__=='__main__':main()
