"""Step 1: what is this? Gemma 4 looks at the photo and names the item the way a reseller would search for it."""
from .llm import chat_json

_S = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "visible_marks": _S,  # logos, labels, text and distinctive design details, written BEFORE naming the item
        "title": _S,          # what a buyer would call it
        "brand": _S,
        "model": _S,
        "category": _S,
        "condition": {"type": "string", "enum": ["new", "like new", "used", "worn", "for parts"]},
        "condition_notes": _S,
        "search_query": _S,   # 2-6 words that find the same item on eBay
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["visible_marks", "title", "brand", "model", "category", "condition", "condition_notes", "search_query", "confidence"],
}

PROMPT = """You are an expert second-hand reseller identifying items from one photo.
First, in visible_marks, list every logo, label, printed text and distinctive design detail you can actually see
(for example a Jumpman logo on a tongue, a model number on a camera, a brand embossed on leather).
Then name exactly what is in the photo from that evidence: brand, model and variant.
Never guess a model you cannot see evidence for: use "unknown" and confidence "low" instead.
search_query: the 2-6 words an eBay seller would type to find this exact item (brand + model + key variant),
no condition words, no colours unless they define the variant.
condition: judge only from what is visible (scuffs, wear, missing parts)."""


def identify(image_bytes):
    return chat_json(PROMPT, "Identify this item for resale.", SCHEMA, image=image_bytes)
