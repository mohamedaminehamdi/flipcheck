"""FlipCheck API, in three steps the app shows as they finish:
  POST /api/identify  photo                    -> what it is (Gemma 4 vision)
  POST /api/price     search query + condition -> live eBay comps + TabPFN price range
  POST /api/listing   photo + item + price     -> a listing ready to paste (Gemma 4)
Also serves the web app from web/.
"""
import io
import json
import os
import time
from collections import defaultdict, deque

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps
from pydantic import BaseModel

load_dotenv()

from . import comps, identify, listing, price  # noqa: E402  (after load_dotenv: modules read env at call time)

app = FastAPI(title="FlipCheck")
MAX_BYTES = 12 * 1024 * 1024
LIMIT, WINDOW = int(os.getenv("RATE_LIMIT", "30")), 600  # requests per IP per 10 minutes
_hits = defaultdict(deque)


def rate_limit(request: Request):
    """Every check spends model and market-data quota, so one visitor can't loop the API."""
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    now, hits = time.time(), _hits[ip]
    while hits and now - hits[0] > WINDOW:
        hits.popleft()
    if len(hits) >= LIMIT:
        raise HTTPException(429, "Too many checks from this connection. Try again in a few minutes.")
    hits.append(now)  # ponytail: in-memory, single instance; move to Redis if we ever run several instances


DOMAINS = {"ebay.com", "ebay.co.uk", "ebay.de", "ebay.fr", "ebay.it", "ebay.es", "ebay.ca", "ebay.com.au"}


async def photo_bytes(photo):
    raw = await photo.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Photo is larger than 12 MB.")
    try:  # phone photos can be huge and rotated: upright, at most 1280 px, JPEG
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    except Exception as exc:
        raise HTTPException(400, "That file isn't a photo we can read.") from exc
    img.thumbnail((1280, 1280))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue()


@app.post("/api/identify", dependencies=[Depends(rate_limit)])
async def api_identify(photo: UploadFile = File(...)):
    return identify.identify(await photo_bytes(photo))


class PriceRequest(BaseModel):
    query: str
    condition: str = "used"
    ebay_domain: str = "ebay.com"


@app.post("/api/price", dependencies=[Depends(rate_limit)])
def api_price(req: PriceRequest):
    query = req.query.strip()[:120]
    if not query:
        raise HTTPException(400, "Search query is empty.")
    if req.ebay_domain not in DOMAINS:
        raise HTTPException(400, "Unsupported eBay site.")
    try:
        market = comps.comps_for(query, req.ebay_domain)
    except comps.MarketUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    return price.price(market, req.condition)


@app.post("/api/listing", dependencies=[Depends(rate_limit)])
async def api_listing(photo: UploadFile = File(...), item: str = Form(...), pricing: str = Form("{}")):
    return listing.write_listing(await photo_bytes(photo), json.loads(item), json.loads(pricing))


@app.get("/api/health")
def health():
    return {"ok": True}


app.mount("/", StaticFiles(directory="web", html=True), name="web")
