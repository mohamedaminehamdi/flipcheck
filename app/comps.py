"""Step 2: what is it selling for right now? Current eBay listings for the item (via SerpApi), cleaned.

These are live asking prices, not sold prices: SerpApi's eBay engine no longer exposes sold listings.
Searches are cached on disk for an hour so repeated checks don't spend the search quota.
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path

import numpy as np
import requests

CACHE = Path(os.getenv("CACHE_DIR", "cache")) / "serpapi"
CONDITION_SCORE = {  # coarse condition scale shared by listings and the user's item
    "new": 4, "brand new": 4, "new with tags": 4, "new without tags": 4, "new with box": 4, "new without box": 3.5,
    "open box": 3.5, "like new": 3.5, "excellent": 3.5, "certified refurbished": 3.5, "refurbished": 3,
    "very good": 3, "pre-owned": 2.5, "used": 2.5, "good": 2.5, "acceptable": 1.5, "worn": 1.5,
    "for parts": 0, "for parts or not working": 0, "parts only": 0,
}
WORDS = re.compile(r"[a-z0-9]+")


class MarketUnavailable(RuntimeError):
    """Live listings couldn't be fetched. The message is safe to show users (no URLs, no keys)."""
LOT = re.compile(r"\b(lot|bundle|set of|x\d|\d+x|pairs)\b", re.I)


def condition_score(text):
    text = (text or "").lower()
    for key in sorted(CONDITION_SCORE, key=len, reverse=True):
        if key in text:
            return CONDITION_SCORE[key]
    return 2.5  # unknown: treat as ordinary used


def similarity(a, b):
    """Share of the query's words that appear in a listing title (0..1)."""
    qa, qb = set(WORDS.findall(a.lower())), set(WORDS.findall(b.lower()))
    return len(qa & qb) / len(qa) if qa else 0.0


def _price(value):
    if isinstance(value, dict):
        value = (value.get("from") or value).get("extracted")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _shipping(text):
    text = (text or "").lower()
    if "free" in text:
        return 0.0
    m = re.search(r"(\d+[.,]?\d*)", text)
    return float(m.group(1).replace(",", ".")) if m else np.nan


def parse(results, query):
    """SerpApi organic_results -> comparable listings with the features the pricing model uses."""
    comps = []
    for r in results:
        price = _price(r.get("price"))
        if r.get("sponsored") or price is None or price <= 0:
            continue
        comps.append({
            "title": r.get("title", ""), "link": r.get("link", ""), "thumbnail": r.get("thumbnail", ""),
            "price": price, "condition": r.get("condition", ""),
            "condition_score": condition_score(r.get("condition")),
            "auction": 1.0 if "auction" in (r.get("buying_format") or "").lower() else 0.0,
            "shipping": _shipping(r.get("shipping")),
            "seller_feedback": float((r.get("seller") or {}).get("positive_feedback_in_percentage") or np.nan),
            "similarity": similarity(query, r.get("title", "")),
        })
    return comps


def clean(comps, min_similarity=0.5):
    """Keep listings that are really this item: similar titles, no lots, no extreme price outliers."""
    kept = [c for c in comps if c["similarity"] >= min_similarity and not LOT.search(c["title"])]
    if len(kept) >= 8:  # trim outliers (accessories, bulk lots) with a robust log-price band
        logp = np.log([c["price"] for c in kept])
        med, mad = np.median(logp), np.median(np.abs(logp - np.median(logp))) or 0.1
        kept = [c for c, lp in zip(kept, logp) if abs(lp - med) <= 3 * 1.4826 * mad]
    return kept


def search(query, ebay_domain="ebay.com", per_page=200):
    """Raw organic results for a query, cached for an hour."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{ebay_domain}|{query.lower().strip()}".encode()).hexdigest()
    path = CACHE / f"{key}.json"
    if path.exists() and time.time() - path.stat().st_mtime < 3600:
        return json.loads(path.read_text())
    key = os.getenv("SERPAPI_KEY")
    if not key:
        raise MarketUnavailable("Live market data isn't configured on this server.")
    try:
        r = requests.get("https://serpapi.com/search.json", timeout=60, params={
            "engine": "ebay", "_nkw": query, "ebay_domain": ebay_domain, "_ipg": per_page, "api_key": key})
    except requests.RequestException:
        raise MarketUnavailable("Couldn't reach the market data service.") from None  # never surface the URL: it holds the key
    if not r.ok:
        raise MarketUnavailable(f"Market data service returned {r.status_code}.")
    results = r.json().get("organic_results", [])
    path.write_text(json.dumps(results))
    return results


def comps_for(query, ebay_domain="ebay.com"):
    return clean(parse(search(query, ebay_domain), query))
