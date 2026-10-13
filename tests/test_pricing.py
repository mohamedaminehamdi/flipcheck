"""Offline checks for comp parsing, cleaning and pricing (no network; TabPFN only in the marked test)."""
import numpy as np
import pytest

from app import comps, price

RESULTS = [
    {"title": "Canon AE-1 35mm Film Camera with 50mm f1.8 Lens", "price": {"from": {"extracted": 120}}, "condition": "Pre-Owned",
     "buying_format": "Buy It Now", "shipping": "+$15.00 shipping", "seller": {"positive_feedback_in_percentage": 99.5}},
    {"title": "Canon AE-1 Program body only", "price": {"from": {"extracted": 80}}, "condition": "Pre-Owned", "buying_format": "Auction",
     "shipping": "Free shipping", "seller": {"positive_feedback_in_percentage": 100}},
    {"title": "Canon AE-1 camera for parts not working", "price": {"from": {"extracted": 35}}, "condition": "For parts or not working",
     "shipping": "Free shipping"},
    {"title": "Lot of 5 Canon AE-1 cameras", "price": {"from": {"extracted": 400}}, "condition": "Pre-Owned"},
    {"title": "Canon AE-1 sponsored", "price": {"from": {"extracted": 150}}, "sponsored": True},
    {"title": "Nikon FM2 camera", "price": {"from": {"extracted": 300}}, "condition": "Used"},
]


def test_parse_skips_sponsored_and_reads_features():
    parsed = comps.parse(RESULTS, "Canon AE-1 50mm")
    assert all("sponsored" not in c["title"] for c in parsed)
    first = parsed[0]
    assert first["price"] == 120 and first["shipping"] == 15.0 and first["auction"] == 0.0
    assert parsed[1]["auction"] == 1.0 and parsed[1]["shipping"] == 0.0
    assert first["condition_score"] == comps.condition_score("pre-owned")


def test_clean_drops_lots_and_other_items():
    kept = comps.clean(comps.parse(RESULTS, "Canon AE-1"))
    titles = [c["title"] for c in kept]
    assert not any("Lot of" in t for t in titles)
    assert not any("Nikon" in t for t in titles)


def test_condition_scale_orders_sensibly():
    s = comps.condition_score
    assert s("Brand New") > s("Pre-Owned") > s("For parts or not working")
    assert s("New with tags") > s("New without box") >= s("Used")


def test_few_comps_fall_back_to_percentiles():
    few = comps.parse(RESULTS[:3], "Canon AE-1")
    out = price.price(few, "used")
    assert out["method"] == "percentiles" and out["quick"] <= out["fair"] <= out["patient"]
    assert price.price(few[:2], "used")["status"] == "not_enough_data"


@pytest.mark.slow
def test_tabpfn_prices_are_ordered_and_follow_condition():
    rng = np.random.default_rng(0)
    table = []
    for i in range(40):
        cond = rng.choice(["Brand New", "Pre-Owned", "For parts or not working"])
        base = {"Brand New": 200, "Pre-Owned": 120, "For parts or not working": 40}[cond]
        table.append({"title": f"Canon AE-1 #{i}", "link": "", "thumbnail": "", "price": float(base * rng.uniform(0.85, 1.15)),
                      "condition": cond, "condition_score": comps.condition_score(cond), "auction": 0.0,
                      "shipping": 10.0, "seller_feedback": 99.0, "similarity": 1.0})
    new, used = price.price(table, "new"), price.price(table, "used")
    assert new["method"] == "tabpfn"
    assert new["quick"] <= new["fair"] <= new["patient"]
    assert new["fair"] > used["fair"]  # condition must matter
    assert 150 < new["fair"] < 250 and 80 < used["fair"] < 160
