"""Step 3: what should this one sell for? TabPFN learns a price model from the live comps, on the spot.

TabPFN is a tabular foundation model: it fits a small table in one forward pass, with no training run, so every
search gets its own model. We use the v2 weights (Apache-2.0 + attribution), which may be hosted commercially.
Prices are modelled in log space (resale prices are skewed) and returned as quantiles:
quick sale = 25th percentile, fair = median, patient = 75th percentile.
"""
import os
from functools import lru_cache

import numpy as np

from .comps import condition_score

os.environ.setdefault("TABPFN_DISABLE_TELEMETRY", "1")
FEATURES = ["condition_score", "auction", "shipping", "seller_feedback", "similarity"]
MIN_FOR_MODEL = 8   # below this, plain percentiles are more honest than a model
MIN_COMPS = 3


@lru_cache(maxsize=1)
def _regressor():
    from tabpfn import TabPFNRegressor
    from tabpfn.constants import ModelVersion

    return TabPFNRegressor.create_default_for_version(ModelVersion.V2, n_estimators=4, device="cpu")


def _row(comp):
    return [comp[f] for f in FEATURES]


def item_row(comps, condition):
    """The user's item as the model sees it: its own condition, a buy-it-now listing, typical shipping."""
    shipping = np.nanmedian([c["shipping"] for c in comps]) if comps else 0.0
    feedback = np.nanmedian([c["seller_feedback"] for c in comps]) if comps else 99.0
    return [condition_score(condition), 0.0, shipping, feedback, 1.0]


def nearest(comps, condition, k=4):
    target = condition_score(condition)
    return sorted(comps, key=lambda c: (-c["similarity"], abs(c["condition_score"] - target), c["price"]))[:k]


def price(comps, condition):
    """Quick / fair / patient prices for an item in `condition`, from cleaned comps."""
    if len(comps) < MIN_COMPS:
        return {"status": "not_enough_data", "comps_used": len(comps)}
    prices = np.array([c["price"] for c in comps])
    if len(comps) < MIN_FOR_MODEL:
        q = np.percentile(prices, [25, 50, 75])
        method = "percentiles"
    else:
        X = np.array([_row(c) for c in comps], dtype=np.float32)
        reg = _regressor()
        reg.fit(X, np.log(prices))
        out = reg.predict(np.array([item_row(comps, condition)], dtype=np.float32),
                          output_type="quantiles", quantiles=[0.25, 0.5, 0.75])
        q = np.exp(np.array([float(np.asarray(v).ravel()[0]) for v in out]))
        method = "tabpfn"
    q = np.sort(q)  # quantiles are monotone in theory; enforce it for display
    return {
        "status": "ok", "method": method, "comps_used": len(comps),
        "quick": round(float(q[0]), 2), "fair": round(float(q[1]), 2), "patient": round(float(q[2]), 2),
        "market_low": round(float(prices.min()), 2), "market_high": round(float(prices.max()), 2),
        "nearest": [{k: c[k] for k in ("title", "price", "condition", "link", "thumbnail")} for c in nearest(comps, condition)],
    }
