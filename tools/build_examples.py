"""Pre-compute the example items so visitors get an answer instantly (no model or market calls).

Usage: uv run tools/build_examples.py
Runs the real pipeline (identify -> live comps -> TabPFN -> listing) on web/examples/*.jpg and writes
web/examples/results.json. Re-run it to refresh the prices; the date is stored so the app can show it.
"""
import datetime as dt
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from app import comps, identify, listing, price  # noqa: E402

EXAMPLES = Path("web/examples")


def main():
    out = {}
    for photo in sorted(EXAMPLES.glob("*.jpg")):
        image = photo.read_bytes()
        item = identify.identify(image)
        pricing = price.price(comps.comps_for(item["search_query"]), item["condition"])
        text = listing.write_listing(image, item, pricing)
        out[photo.stem] = {"item": item, "price": pricing, "listing": text, "checked": dt.date.today().isoformat()}
        fair = pricing.get("fair", "n/a")
        print(f"{photo.stem}: {item['title']} | query '{item['search_query']}' | fair {fair} from {pricing.get('comps_used')} comps")
    (EXAMPLES / "results.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
