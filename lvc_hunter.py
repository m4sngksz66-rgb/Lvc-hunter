#!/usr/bin/env python3
"""
LVC Hunter v0.2
Prototype scanner for finding likely Levi's Vintage Clothing / LVC jeans in product photos.

What it does:
- OCR: searches for LVC-ish patch text.
- Visual features: learns from positive/negative reference images.
- Rule scoring: boosts/penalizes known patch phrases and false positives.
- Optional crawler: downloads listing images from a search/listing page, then scans them.

Use:
  python lvc_hunter.py train dataset/positive dataset/negative --model models/lvc_model.joblib
  python lvc_hunter.py scan dataset/positive dataset/negative --model models/lvc_model.joblib --out results.csv
  python lvc_hunter.py crawl "https://www.sellpy.se/search?query=levis%20501" --download-dir sellpy_images --limit 50

Install:
  pip install opencv-python pillow pytesseract numpy scikit-learn joblib requests beautifulsoup4 playwright
  playwright install chromium
  # plus system tesseract: brew install tesseract / sudo apt install tesseract-ocr
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, List, Tuple, Optional
from urllib.parse import urljoin

import cv2
import joblib
import numpy as np
import pytesseract
import requests
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# Strong positive signals from your target list and examples.
POSITIVE_PATTERNS = {
    r"\bS?501\s*[X×]{2}\b": 16,
    r"\b551\s*Z\s*[X×]{2}\b": 14,
    r"\b502\s*[X×]{2}\b": 12,
    r"\b503\s*A\s*[X×]{2}\b": 14,
    r"\b503\s*B\s*[X×]{2}\b": 14,
    r"\b201\s*[X×]{2}\b": 10,
    r"CARE\s+INSTRUCTIONS\s+INSIDE\s+GARMENT": 12,
    r"MADE\s+IN\s+U\.?S\.?A\.?": 10,
    r"MADE\s+IN\s+USA": 10,
    r"WPL\s*423": 4,
    r"QUALITY\s+CLOTHING": 3,
    r"ORIGINAL\s+RIVETED": 3,
    r"\b0117\b": 8,
    r"\b0217\b": 8,
}

# Negative signals from your “do not look for” examples.
NEGATIVE_PATTERNS = {
    r"WATER\s*<?\s*LESS": -22,
    r"LEVI\s+STRAUSS\s+DE\s+M[EÉ]XICO": -18,
    r"MEXICO|BANGLADESH|EGYPT|PAKISTAN|TURKEY|CHINA|CAMBODIA|VIETNAM|SRI\s*LANKA": -9,
    r"\b550\b": -18,
    r"\b527\b": -18,
    r"\b505\b": -12,
    r"\b502\s*TM\b": -14,
    r"\b501\s*['’´`]\s*93\b": -14,
    r"GENUINE\s+QUALITY\s+CLOTHING": -10,
    r"EVERY\s+GARMENT\s+GUARANTEED": -6,
    r"LEVI\s+STRAUSS\s+DE\s+BRASIL": -14,
}

@dataclass
class ScanResult:
    image: str
    score_total: float
    verdict: str
    ml_probability: Optional[float]
    rule_score: int
    visual_rule_score: int
    positive_hits: str
    negative_hits: str
    ocr_excerpt: str


def normalize_ocr(text: str) -> str:
    t = text.upper()
    replacements = {
        "SOI": "501", "S0I": "501", "5OI": "501", "5O1": "501", "50I": "501",
        "S0L": "501", "SOL": "501", "SO1": "501", "×": "X",
        "U S A": "USA", "U.S A": "USA", "U.S.A": "USA",
        "GARMENT 100": "GARMENT 100", "1OO": "100",
    }
    for a, b in replacements.items():
        t = t.replace(a, b)
    t = re.sub(r"[^A-Z0-9\.\s<'’`×X]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def iter_images(root: Path) -> Iterable[Path]:
    if root.is_file() and root.suffix.lower() in IMAGE_EXTS:
        yield root
    elif root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.suffix.lower() in IMAGE_EXTS:
                yield p


def read_img(path: Path, max_side: int = 900) -> Optional[np.ndarray]:
    img = cv2.imread(str(path))
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = max_side / max(h, w)
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return img


def preprocess_variants(path: Path) -> List[Image.Image]:
    img = read_img(path, max_side=1300)
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    variants = []
    for clip in (2.0,):
        clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(8, 8)).apply(gray)
        variants.append(Image.fromarray(clahe))
        thresh = cv2.adaptiveThreshold(clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 31, 9)
        variants.append(Image.fromarray(thresh))
    return variants


def ocr_path(path: Path) -> str:
    texts = []
    for im in preprocess_variants(path):
        for psm in (6,):
            try:
                texts.append(pytesseract.image_to_string(im, config=f"--psm {psm}", timeout=2))
            except Exception:
                pass
    return normalize_ocr("\n".join(texts))


def score_text(text: str) -> Tuple[int, List[str], List[str]]:
    score = 0
    pos, neg = [], []
    for pat, pts in POSITIVE_PATTERNS.items():
        if re.search(pat, text):
            score += pts
            pos.append(pat)
    for pat, pts in NEGATIVE_PATTERNS.items():
        if re.search(pat, text):
            score += pts
            neg.append(pat)
    return score, pos, neg


def visual_rule_score(path: Path) -> int:
    """Cheap prior: red-on-tan patch is good; big grey/black patch is bad."""
    img = read_img(path, max_side=900)
    if img is None:
        return 0
    h, w = img.shape[:2]
    # Most reference/Sellpy rear photos have patch in upper half.
    crop = img[: int(h * 0.60), :]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    area = crop.shape[0] * crop.shape[1]

    red1 = cv2.inRange(hsv, np.array([0, 45, 35]), np.array([12, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([165, 45, 35]), np.array([180, 255, 255]))
    red_ratio = cv2.countNonZero(red1 | red2) / area

    tan = cv2.inRange(hsv, np.array([8, 18, 65]), np.array([38, 190, 255]))
    tan_ratio = cv2.countNonZero(tan) / area

    gray = cv2.inRange(hsv, np.array([0, 0, 20]), np.array([180, 70, 145]))
    gray_ratio = cv2.countNonZero(gray) / area

    score = 0
    if red_ratio > 0.002 and tan_ratio > 0.012:
        score += 5
    if red_ratio > 0.006 and tan_ratio > 0.030:
        score += 5
    if red_ratio > 0.010 and tan_ratio > 0.045:
        score += 3
    if gray_ratio > 0.14 and red_ratio < 0.002:
        score -= 10
    return score


def image_features(path: Path) -> np.ndarray:
    img = read_img(path, max_side=512)
    if img is None:
        return np.zeros(140, dtype=np.float32)
    # Crop upper 70%; patch tends to be there. If no patch, full image still gives denim/label cues.
    h, w = img.shape[:2]
    crop = img[: int(h * 0.70), :]
    crop = cv2.resize(crop, (224, 224), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)

    feats = []
    # HSV histograms.
    for ch, bins, rng in [(0, 24, [0, 180]), (1, 16, [0, 256]), (2, 16, [0, 256])]:
        hist = cv2.calcHist([hsv], [ch], None, [bins], rng).flatten()
        hist = hist / (hist.sum() + 1e-6)
        feats.extend(hist.tolist())
    # LAB means/stds.
    feats.extend(np.mean(lab.reshape(-1, 3), axis=0).tolist())
    feats.extend(np.std(lab.reshape(-1, 3), axis=0).tolist())

    area = hsv.shape[0] * hsv.shape[1]
    masks = {
        "red1": cv2.inRange(hsv, np.array([0, 45, 35]), np.array([12, 255, 255])),
        "red2": cv2.inRange(hsv, np.array([165, 45, 35]), np.array([180, 255, 255])),
        "tan": cv2.inRange(hsv, np.array([8, 18, 65]), np.array([38, 190, 255])),
        "blue": cv2.inRange(hsv, np.array([85, 30, 25]), np.array([135, 255, 230])),
        "gray": cv2.inRange(hsv, np.array([0, 0, 20]), np.array([180, 70, 145])),
        "white": cv2.inRange(hsv, np.array([0, 0, 185]), np.array([180, 80, 255])),
    }
    red = masks["red1"] | masks["red2"]
    for m in [red, masks["tan"], masks["blue"], masks["gray"], masks["white"]]:
        feats.append(cv2.countNonZero(m) / area)

    # Edge density can help separate close patch shots vs product shots; not decisive.
    gray_img = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray_img, 80, 160)
    feats.append(cv2.countNonZero(edges) / area)
    return np.array(feats, dtype=np.float32)


def train_model(pos_dir: Path, neg_dir: Path, model_path: Path) -> None:
    pos = list(iter_images(pos_dir))
    neg = list(iter_images(neg_dir))
    if len(pos) < 3 or len(neg) < 3:
        raise SystemExit("Need at least 3 positive and 3 negative images.")
    X = np.vstack([image_features(p) for p in pos + neg])
    y = np.array([1] * len(pos) + [0] * len(neg))
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced"))
    clf.fit(X, y)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": clf, "positive_count": len(pos), "negative_count": len(neg)}, model_path)
    print(f"Saved model: {model_path}")
    print(f"Training images: {len(pos)} positive, {len(neg)} negative")


def load_model(path: Optional[Path]):
    if not path or not path.exists():
        return None
    return joblib.load(path)["model"]


def verdict(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 45:
        return "MAYBE"
    return "LOW"


def scan_image(path: Path, model=None, use_ocr: bool = True) -> ScanResult:
    text = ocr_path(path) if use_ocr else ""
    rule, pos, neg = score_text(text)
    vis = visual_rule_score(path)
    ml_prob = None
    ml_points = 0
    if model is not None:
        try:
            ml_prob = float(model.predict_proba(image_features(path).reshape(1, -1))[0, 1])
            ml_points = int(round(ml_prob * 60))
        except Exception:
            ml_prob = None
    total = rule + vis + ml_points
    return ScanResult(
        image=str(path),
        score_total=round(float(total), 2),
        verdict=verdict(total),
        ml_probability=None if ml_prob is None else round(ml_prob, 4),
        rule_score=rule,
        visual_rule_score=vis,
        positive_hits="; ".join(pos),
        negative_hits="; ".join(neg),
        ocr_excerpt=text[:650],
    )


def write_csv(results: List[ScanResult], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()) if results else ["image"])
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))


def cmd_train(args):
    train_model(Path(args.positive), Path(args.negative), Path(args.model))


def cmd_scan(args):
    model = load_model(Path(args.model)) if args.model else None
    paths = [p for root in args.paths for p in iter_images(Path(root))]
    results = [scan_image(p, model, use_ocr=not args.no_ocr) for p in paths]
    results.sort(key=lambda r: r.score_total, reverse=True)
    write_csv(results, Path(args.out))
    for r in results[: args.top]:
        ml = "-" if r.ml_probability is None else f"{r.ml_probability:.2f}"
        print(f"{r.score_total:>5} {r.verdict:<5} ML={ml:<4} {Path(r.image).name} +[{r.positive_hits}] -[{r.negative_hits}]")
    print(f"\nSaved {len(results)} rows to {args.out}")


def safe_name(url: str) -> str:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    ext = Path(url.split("?")[0]).suffix.lower()
    if ext not in IMAGE_EXTS:
        ext = ".jpg"
    return h + ext


def download_image(url: str, out_dir: Path) -> Optional[Path]:
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200 or not r.content:
            return None
        p = out_dir / safe_name(url)
        p.write_bytes(r.content)
        return p
    except Exception:
        return None


def cmd_crawl(args):
    """Simple Playwright crawler. Use gently; don't hammer Sellpy."""
    out_dir = Path(args.download_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise SystemExit("Install playwright first: pip install playwright && playwright install chromium") from e

    image_urls = set()
    product_urls = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show_browser)
        page = browser.new_page(user_agent="Mozilla/5.0")
        page.goto(args.url, wait_until="networkidle", timeout=60000)
        for _ in range(args.scrolls):
            page.mouse.wheel(0, 3500)
            page.wait_for_timeout(args.delay_ms)
        hrefs = page.locator("a").evaluate_all("els => els.map(a => a.href).filter(Boolean)")
        product_urls = {h for h in hrefs if "/item/" in h or "/p/" in h or "/product/" in h}
        if args.limit:
            product_urls = set(list(product_urls)[: args.limit])
        print(f"Found {len(product_urls)} product-like links")
        for i, u in enumerate(sorted(product_urls), 1):
            print(f"[{i}/{len(product_urls)}] {u}")
            try:
                page.goto(u, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(args.delay_ms)
                imgs = page.locator("img").evaluate_all("imgs => imgs.map(img => img.src).filter(Boolean)")
                for src in imgs:
                    if src.startswith("http"):
                        image_urls.add(src)
            except Exception as e:
                print(f"  skip: {e}")
        browser.close()
    print(f"Downloading {len(image_urls)} images")
    saved = []
    for u in sorted(image_urls):
        p = download_image(u, out_dir)
        if p:
            saved.append(p)
    print(f"Saved {len(saved)} images to {out_dir}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Find likely Levi's Vintage Clothing from photos.")
    sub = parser.add_subparsers(required=True)

    t = sub.add_parser("train", help="Train simple visual model from positive/negative folders")
    t.add_argument("positive")
    t.add_argument("negative")
    t.add_argument("--model", default="models/lvc_model.joblib")
    t.set_defaults(func=cmd_train)

    s = sub.add_parser("scan", help="Scan local images/folders")
    s.add_argument("paths", nargs="+")
    s.add_argument("--model", default="models/lvc_model.joblib")
    s.add_argument("--out", default="results/lvc_results.csv")
    s.add_argument("--top", type=int, default=30)
    s.add_argument("--no-ocr", action="store_true", help="Fast mode: skip Tesseract OCR and use visual model/rules only")
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("crawl", help="Download images from a Sellpy/search/listing page")
    c.add_argument("url")
    c.add_argument("--download-dir", default="sellpy_images")
    c.add_argument("--limit", type=int, default=40)
    c.add_argument("--scrolls", type=int, default=6)
    c.add_argument("--delay-ms", type=int, default=1500)
    c.add_argument("--show-browser", action="store_true")
    c.set_defaults(func=cmd_crawl)

    args = parser.parse_args(argv)
    args.func(args)

if __name__ == "__main__":
    main()
