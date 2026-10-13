# FlipCheck

**Snap a thrift find. Get a fair resale price and a listing ready to paste.**

For eBay, Vinted and car-boot flippers who price dozens of items a week and hate the research.

```
photo ──> Gemma 4 (vision) ──> "Canon AE-1 with 50mm f/1.8, used"
      ──> live eBay listings for that search (SerpApi)
      ──> TabPFN learns a price model from those listings, on the spot
      ──> quick sale · fair · patient price, plus the closest listings
      ──> Gemma 4 writes the title, description and item specifics
```

## How the price works

1. **Identify.** Gemma 4 names the item from the photo: brand, model, visible condition and the search a seller would type. You can edit the search before anything is priced.
2. **Market.** Up to 200 current eBay listings for that search, via SerpApi. Lots, sponsored listings, unrelated titles and price outliers are dropped.
3. **Price.** [TabPFN](https://github.com/PriorLabs/TabPFN) is a tabular foundation model. It fits that small table in one pass, with no training run, so every search gets its own model.
   - **Inputs:** condition, auction or buy-it-now, shipping, seller feedback, and title similarity.
   - **Output:** the 25th, 50th and 75th percentile of log price for *your* item's condition, shown as **quick sale**, **fair** and **if you can wait**.
4. **List.** Gemma 4 writes an eBay title (80 characters max), an honest description and item specifics, using only what it can see.

**Honest limits**
- These are **live asking prices**, not sold prices. SerpApi's eBay engine no longer exposes sold listings, and sold items usually go for a bit less. The app says so on every result.
- With fewer than 8 good comparable listings, the app falls back to plain percentiles. With fewer than 3, it says there isn't enough data.

## Why open models

Resellers check a lot of items, and margins are thin. A pricing tool only works as a side hustle if each check costs almost nothing:
- **Gemma 4** has open weights, so it can be self-hosted or rented from any provider. You aren't locked into one vendor's price per image.
- **TabPFN v2 weights** (Prior Labs License: Apache-2.0 plus attribution) **may be hosted commercially**. The newer TabPFN weights are non-commercial. "Built with TabPFN."
- **No training pipeline.** TabPFN learns from each search's fresh listings, so prices are always current.

## Run it

```bash
cp .env.example .env            # SERPAPI_KEY, plus a Gemma 4 endpoint (default: local Ollama gemma4:e4b)
uv run uvicorn app.main:app --reload
open http://localhost:8000
```

- `uv run tools/check_llm.py`: checks that your Gemma endpoint accepts images and returns JSON.
- `uv run tools/build_examples.py`: pre-computes the example items so they answer instantly.
- `uv run pytest`: tests. CI also runs the real TabPFN test.

**Deploy:** `render.yaml` is a Render blueprint (2 GB plan, CPU-only PyTorch). Set `SERPAPI_KEY`, `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` in Render. Any OpenAI-compatible Gemma 4 endpoint works, for example DigitalOcean serverless inference (`gemma-4-31B-it`) or OpenRouter (`google/gemma-4-31b-it`).

## API

| Endpoint | In | Out |
|---|---|---|
| `POST /api/identify` | photo | item: title, brand, model, condition, search query, confidence |
| `POST /api/price` | `{query, condition, ebay_domain}` | quick / fair / patient, market range, closest listings |
| `POST /api/listing` | photo, item, price | eBay title, description, item specifics |

**Guards:**
- A per-IP rate limit, keyed on the proxy-written address, with IPv6 grouped per /64.
- Bodies over 12 MB refused before they're read.
- Images resized server-side.
- API keys never appear in errors.

## Credits

- Example photos from Wikimedia Commons:
  - Air Jordan IV by Osyffar (CC0)
  - Canon AE-1 by Cburnett (CC BY-SA 3.0)
  - Game Boy by Evan-Amos (public domain)
  - Coach Borough bag by Kristiane Cyrus (CC BY-SA 3.0)
- [Gemma 4](https://ai.google.dev/gemma) by Google. [TabPFN](https://github.com/PriorLabs/TabPFN) by Prior Labs. Market data via [SerpApi](https://serpapi.com).

MIT licensed. Built for the [DEV Hacktoberfest Open-Source AI Challenge: Side Hustle](https://dev.to/challenges/hf26).
