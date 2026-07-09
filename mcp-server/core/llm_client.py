"""
LLM Client — Groq (primary free-tier) → Google AI Studio → OpenRouter → Ollama fallback.
Supports both streaming and JSON-mode responses.
"""
import json
import logging
import os
from typing import Any, AsyncGenerator

import httpx

logger = logging.getLogger("ikp.llm")

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash-lite")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


async def _groq_chat(messages: list[dict], temperature: float = 0.3, json_mode: bool = False) -> str | None:
    if not GROQ_API_KEY:
        return None
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 4096,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(f"{GROQ_BASE_URL}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning("Groq failed: %s", e)
        return None


async def _google_chat(messages: list[dict], temperature: float = 0.3) -> str | None:
    if not GOOGLE_API_KEY:
        return None
    # Convert OpenAI format → Google Gemini format
    contents = []
    for m in messages:
        role = "user" if m["role"] in ("user", "system") else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload = {"contents": contents, "generationConfig": {"temperature": temperature, "maxOutputTokens": 4096}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GOOGLE_MODEL}:generateContent?key={GOOGLE_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            resp = await c.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.warning("Google AI Studio failed: %s", e)
        return None


async def _ollama_chat(messages: list[dict], temperature: float = 0.3) -> str | None:
    payload = {"model": OLLAMA_MODEL, "messages": messages, "stream": False,
               "options": {"temperature": temperature}}
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            resp = await c.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
    except Exception as e:
        logger.warning("Ollama failed: %s", e)
        return None


async def chat(
    prompt: str,
    system: str = "",
    temperature: float = 0.3,
) -> str:
    """Multi-tier LLM chat — Groq → Google AI Studio → Ollama."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    for fn in (_groq_chat, _google_chat, _ollama_chat):
        result = await fn(messages, temperature=temperature)
        if result:
            return result

    return "⚠️ All LLM providers unavailable. Check API keys and Ollama."


async def json_chat(
    prompt: str,
    system: str = "",
    temperature: float = 0.1,
) -> dict | None:
    """Chat with JSON output mode — tries Groq JSON mode first."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Try Groq with JSON mode
    text = await _groq_chat(messages, temperature=temperature, json_mode=True)
    if not text:
        # Fallback: add JSON instruction and use standard chat
        messages[-1]["content"] += "\n\nRespond ONLY with valid JSON, no explanation."
        text = await _google_chat(messages, temperature=temperature)
    if not text:
        text = await _ollama_chat(messages, temperature=temperature)

    if not text:
        return None

    # Parse JSON
    try:
        # Strip markdown fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed: %s | text: %s", e, text[:200])
        return None
