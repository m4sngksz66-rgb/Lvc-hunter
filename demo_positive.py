"""Reproducible positive *local* example; not a marketplace live test."""
import argparse, csv, json, subprocess, sys
from pathlib import Path
import joblib
from lvc_hunter import image_features

def main():
 p=argparse.ArgumentParser();p.add_argument('positive_dir');p.add_argument('--model',default='models/lvc_model_v06.joblib');p.add_argument('--out',default='results/positive_demo.json');a=p.parse_args()
 model=joblib.load(a.model)['model']
 imgs=[x for x in Path(a.positive_dir).rglob('*') if x.suffix.lower() in ('.jpg','.jpeg','.png','.webp')]
 ranked=[]
 for f in imgs:
  try: ranked.append((float(model.predict_proba(image_features(f).reshape(1,-1))[0,1]),str(f)))
  except Exception: pass
 if not ranked: raise SystemExit('No usable images')
 ranked.sort(reverse=True)
 score,path=ranked[0]
 output={'example_type':'known_positive_training_pool_not_independent','image':path,'model_score':round(score,4),'passes_review_threshold':score>=.25,'price_bargain_verified':False,'warning':'This is a known labeled positive image, potentially in model training; not evidence of marketplace recall.'}
 target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(output,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
