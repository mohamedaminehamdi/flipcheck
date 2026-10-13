"""One OpenAI-compatible client for Gemma 4: local Ollama in development, any hosted provider in production.

Configured with LLM_BASE_URL, LLM_MODEL and LLM_API_KEY (see .env.example).
"""
import base64
import json
import os

import requests


def chat_json(system, user_text, schema, image=None, temperature=0.2, timeout=180):
    """Ask the model for JSON matching `schema`. `image` is raw JPEG/PNG bytes (optional)."""
    content = [{"type": "text", "text": user_text}]
    if image:
        data_url = "data:image/jpeg;base64," + base64.b64encode(image).decode()
        content.append({"type": "image_url", "image_url": {"url": data_url}})
    body = {
        "model": os.getenv("LLM_MODEL", "gemma4:e4b"),
        "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "schema": schema}},
    }
    r = requests.post(
        os.getenv("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/") + "/chat/completions",
        json=body, timeout=timeout,
        headers={"Authorization": f"Bearer {os.getenv('LLM_API_KEY', 'ollama')}"},
    )
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])
