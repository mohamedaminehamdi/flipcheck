"""Does the configured Gemma 4 endpoint accept images and return schema JSON? One call, one photo.

Usage: uv run tools/check_llm.py [photo.jpg]
Reads LLM_BASE_URL / LLM_MODEL / LLM_API_KEY from .env and prints the identification plus how long it took.
"""
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from app.identify import identify  # noqa: E402


def main():
    photo = Path(sys.argv[1] if len(sys.argv) > 1 else "web/examples/sneaker.jpg")
    print(f"{os.getenv('LLM_MODEL')} at {os.getenv('LLM_BASE_URL')}")
    t = time.time()
    result = identify(photo.read_bytes())
    print(json.dumps(result, indent=1, ensure_ascii=False))
    print(f"{time.time() - t:.1f}s")


if __name__ == "__main__":
    main()
