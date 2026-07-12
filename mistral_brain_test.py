"""
Phase 0 Verification — Mistral Medium 3.5 Brain Test
=====================================================
Run this script BEFORE starting the MCP server to confirm:
  1. The openai package is installed correctly
  2. Your NVIDIA API key is valid
  3. mistral-medium-3.5-128b responds to a non-streaming call
  4. mistral-medium-3.5-128b responds to a streaming call (clean text only)
  5. JSON-mode output can be parsed

Usage:
    cd mcp-server
    pip install openai python-dotenv
    python ../test_glm_brain.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# ── Load .env from project root ───────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print(f"✅  Loaded .env from {env_path}")
else:
    print("⚠️   No .env found — reading NVIDIA_API_KEY from system environment")

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "z-ai/glm-5.2")

if not NVIDIA_API_KEY:
    print("❌  NVIDIA_API_KEY is not set. Add it to your .env file.")
    sys.exit(1)

print(f"\n🔑  API Key   : {NVIDIA_API_KEY[:12]}...{NVIDIA_API_KEY[-4:]}")
print(f"🤖  Model     : {LLM_MODEL}")
print(f"🌐  Endpoint  : https://integrate.api.nvidia.com/v1")
print(f"⚡  Why Mistral: ~3-5x faster inference than GLM-5.2 on same hardware\n")

# ── Import client ─────────────────────────────────────────────────────────────
try:
    from openai import AsyncOpenAI
    print("✅  openai package found")
except ImportError:
    print("❌  openai not installed. Run: pip install openai")
    sys.exit(1)

client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)

COMMON_PARAMS = dict(
    model=LLM_MODEL,
    temperature=0.4,
    top_p=0.91,
    max_tokens=512,   # short for testing
    seed=42,
)


# ── TEST 1: Non-streaming call ────────────────────────────────────────────────
async def test_basic_chat():
    print("=" * 60)
    print("TEST 1 — Basic (non-streaming) chat")
    print("=" * 60)
    prompt = "In one sentence, confirm you are the AI brain for an Industrial Knowledge Platform."
    try:
        resp = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            **COMMON_PARAMS,
        )
        answer = resp.choices[0].message.content or ""
        print(f"✅  Response: {answer.strip()}\n")
        return True
    except Exception as e:
        print(f"❌  FAILED: {e}\n")
        return False


# ── TEST 2: Streaming call ────────────────────────────────────────────────────
async def test_streaming_chat():
    print("=" * 60)
    print("TEST 2 — Streaming chat (clean token-by-token, no raw dicts)")
    print("=" * 60)
    prompt = "List 3 common industrial equipment failure modes in one line each."
    print("🔄  Streaming response: ", end="", flush=True)
    full_text = ""
    raw_dict_printed = False
    try:
        stream = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            **COMMON_PARAMS,
        )
        async for chunk in stream:
            # Guard 1: skip non-chunk objects (prevents raw dict printing)
            if not hasattr(chunk, "choices"):
                continue
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            # Guard 2: skip finish chunks
            if getattr(choice, "finish_reason", None) is not None:
                continue
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue
            content = getattr(delta, "content", None)
            if content is not None:
                print(content, end="", flush=True)
                full_text += content
        print(f"\n✅  Stream complete. Total chars: {len(full_text)}")
        print(f"✅  No raw dict output detected\n")
        return True
    except Exception as e:
        print(f"\n❌  FAILED: {e}\n")
        return False


# ── TEST 3: JSON-mode call ────────────────────────────────────────────────────
async def test_json_mode():
    print("=" * 60)
    print("TEST 3 — JSON structured output")
    print("=" * 60)
    prompt = (
        "You are an industrial NER system. Extract entities from this text and "
        "return ONLY valid JSON, no explanation:\n\n"
        "Text: 'Pump P-101A showed bearing failure at 85°C on 15-Jan-2024. "
        "Ref: OISD-154. Technician: Arjun Kumar.'\n\n"
        "Return JSON with keys: equipment_tags, process_parameters, regulatory_refs, persons, dates"
    )
    try:
        resp = await client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            **COMMON_PARAMS,
        )
        raw = resp.choices[0].message.content or ""
        # Strip markdown fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            cleaned = inner.strip()
        parsed = json.loads(cleaned)
        print(f"✅  Parsed JSON:\n{json.dumps(parsed, indent=2)}\n")
        return True
    except json.JSONDecodeError:
        print(f"⚠️   Response was not valid JSON:\n{raw}\n")
        return False
    except Exception as e:
        print(f"❌  FAILED: {e}\n")
        return False


# ── TEST 4: Industrial domain test ───────────────────────────────────────────
async def test_industrial_domain():
    print("=" * 60)
    print("TEST 4 — Industrial domain knowledge check")
    print("=" * 60)
    prompt = (
        "A centrifugal pump P-202 shows vibration of 12 mm/s and bearing temperature "
        "rising to 95°C over the last 48 hours. Discharge pressure dropped 20%. "
        "What is the most likely root cause and recommended immediate action? "
        "Answer in 3 bullet points."
    )
    try:
        resp = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an expert industrial maintenance engineer."},
                {"role": "user", "content": prompt},
            ],
            stream=False,
            **COMMON_PARAMS,
        )
        answer = resp.choices[0].message.content or ""
        print(f"✅  Industrial Response:\n{answer.strip()}\n")
        return True
    except Exception as e:
        print(f"❌  FAILED: {e}\n")
        return False


# ── Run all tests ─────────────────────────────────────────────────────────────
async def main():
    results = {}
    results["basic_chat"]       = await test_basic_chat()
    results["streaming_chat"]   = await test_streaming_chat()
    results["json_mode"]        = await test_json_mode()
    results["industrial_domain"] = await test_industrial_domain()

    print("=" * 60)
    print("PHASE 0 VERIFICATION SUMMARY")
    print("=" * 60)
    all_passed = True
    for test, passed in results.items():
        icon = "✅" if passed else "❌"
        print(f"  {icon}  {test}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉  ALL TESTS PASSED — GLM-5.2 brain is ready!")
        print("    You can now proceed to Phase 1 (Embedding Engine).")
    else:
        print("\n⚠️   Some tests failed. Fix the issues above before proceeding.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
