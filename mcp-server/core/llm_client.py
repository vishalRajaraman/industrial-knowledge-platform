"""
LLM Client — GLM-5.2 via NVIDIA NIM API (OpenAI-compatible).
Single brain. No fallbacks. Streaming + JSON-mode supported.
"""
import json
import logging
import os

from openai import AsyncOpenAI

logger = logging.getLogger("ikp.llm")

# ── Config ────────────────────────────────────────────────────────────────────
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
LLM_MODEL = os.getenv("LLM_MODEL", "mistralai/mistral-medium-3.5-128b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.4"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "0.91"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "16384"))
LLM_SEED = int(os.getenv("LLM_SEED", "42"))

# ── Singleton async client (reused across calls) ──────────────────────────────
_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not NVIDIA_API_KEY:
            raise RuntimeError(
                "NVIDIA_API_KEY is not set. Add it to your .env file.\n"
                "Get your key from: https://build.nvidia.com"
            )
        _client = AsyncOpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=NVIDIA_API_KEY,
        )
    return _client


# ── Core chat function ────────────────────────────────────────────────────────

async def chat(
    prompt: str,
    system: str = "",
    temperature: float | None = None,
) -> str:
    """
    Send a prompt to GLM-5.2 and return the full response text.

    Args:
        prompt:      The user message / query.
        system:      Optional system instruction to set model behaviour.
        temperature: Override default temperature (0.4) if needed.

    Returns:
        The model's response as a plain string.

    Raises:
        RuntimeError: If NVIDIA_API_KEY is missing.
        Exception:    Propagates API errors so callers can handle them.
    """
    client = _get_client()
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        completion = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=temperature if temperature is not None else LLM_TEMPERATURE,
            top_p=LLM_TOP_P,
            max_tokens=LLM_MAX_TOKENS,
            seed=LLM_SEED,
            stream=False,   # non-streaming for synchronous agent calls
        )
        return completion.choices[0].message.content or ""
    except Exception as e:
        logger.error("GLM-5.2 (NVIDIA) call failed: %s", e)
        raise


# ── Streaming chat ────────────────────────────────────────────────────────────

async def stream_chat(
    prompt: str,
    system: str = "",
    temperature: float | None = None,
):
    """
    Async generator that yields response tokens as they arrive.
    Use this for the /query/stream endpoint.

    Usage:
        async for token in stream_chat("your prompt"):
            print(token, end="", flush=True)
    """
    client = _get_client()
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        stream = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=temperature if temperature is not None else LLM_TEMPERATURE,
            top_p=LLM_TOP_P,
            max_tokens=LLM_MAX_TOKENS,
            seed=LLM_SEED,
            stream=True,
        )
        async for chunk in stream:
            # Guard 1: must be a streaming chunk object, not a raw dict
            if not hasattr(chunk, "choices"):
                continue
            # Guard 2: must have at least one choice
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            # Guard 3: skip finish chunks (finish_reason='stop', delta.content is None)
            if getattr(choice, "finish_reason", None) is not None:
                continue
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue
            content = getattr(delta, "content", None)
            if content is not None:
                yield content
    except Exception as e:
        logger.error("Mistral streaming failed: %s", e)
        raise


# ── JSON-mode chat ────────────────────────────────────────────────────────────

async def json_chat(
    prompt: str,
    system: str = "",
    temperature: float = 0.1,
) -> dict | None:
    """
    Request a structured JSON response from GLM-5.2.
    Appends a strict JSON instruction to the prompt and strips markdown fences.

    Args:
        prompt:      The query. Include the desired JSON schema in your prompt.
        system:      Optional system context.
        temperature: Low temperature (0.1) for deterministic JSON output.

    Returns:
        Parsed dict, or None if parsing fails.
    """
    json_instruction = "\n\nRespond ONLY with valid JSON. No explanation, no markdown fences, no extra text."
    full_prompt = prompt + json_instruction

    try:
        raw = await chat(full_prompt, system=system, temperature=temperature)
    except Exception as e:
        logger.error("json_chat: LLM call failed: %s", e)
        return None

    # ── Strip markdown fences if the model wraps anyway ──────────────────────
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        # parts[1] is the content between first pair of fences
        inner = parts[1]
        if inner.startswith("json"):
            inner = inner[4:]
        cleaned = inner.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("json_chat: JSON parse failed — %s | raw: %s", e, raw[:300])
        return None
