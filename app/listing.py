"""Step 4: a listing ready to paste. Gemma 4 writes it from the photo and what we already know about the item."""
import json

from .llm import chat_json

_S = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "title": _S,
        "description": _S,
        "specifics": {"type": "array", "items": {
            "type": "object", "properties": {"name": _S, "value": _S}, "required": ["name", "value"]}},
    },
    "required": ["title", "description", "specifics"],
}

PROMPT = """You write eBay listings that sell. Use only facts from the identification and what is visible in the photo.
- title: at most 80 characters, searchable keywords first (brand, model, variant, size if visible), no hype words, no emojis.
- description: 3 short paragraphs: what it is, its visible condition stated honestly (mention flaws), and what's included.
  Never invent specifications, sizes, serial numbers or accessories you cannot see.
- specifics: eBay item specifics (Brand, Model, Type, Color, Condition, ...) only where known."""


def write_listing(image_bytes, identification, price_info):
    facts = {k: identification.get(k) for k in ("title", "brand", "model", "category", "condition", "condition_notes")}
    note = f"Suggested price: {price_info['fair']}" if price_info.get("status") == "ok" else ""
    listing = chat_json(PROMPT, f"Identification: {json.dumps(facts)}\n{note}\nWrite the listing.", SCHEMA, image=image_bytes)
    listing["title"] = listing["title"][:80]  # eBay's hard limit
    return listing
