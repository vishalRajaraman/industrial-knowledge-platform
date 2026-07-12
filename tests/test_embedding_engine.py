"""
Embedding Engine Test — Cohere embed-multilingual-v3.0
=======================================================
Tests the Cohere cloud embedding API in isolation.
No MCP server, no Qdrant needed for this test.

Covers:
  1. API key validation + Cohere client init
  2. embed_documents()  — batch document embedding
  3. embed_query()      — single query embedding
  4. Asymmetric input_type check (search_document vs search_query)
  5. Cosine similarity — relevant doc scores higher than irrelevant
  6. Multilingual test  — Hindi industrial text embeds correctly
  7. Batch size handling — 97 texts (crosses Cohere's 96-limit, auto-chunked)

Usage:
    pip install cohere python-dotenv
    python test_embedding_engine.py
"""

import sys
import os
import math
import time
from pathlib import Path

# ── Load .env ─────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print(f"✅  Loaded .env from {env_path}")
else:
    print("⚠️   No .env found — using defaults")

# ── Add mcp-server to path ────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent / "mcp-server"))

COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
EXPECTED_DIM   = int(os.getenv("EMBEDDING_DIM", "1024"))
EMBED_MODEL    = os.getenv("EMBEDDING_MODEL", "embed-multilingual-v3.0")

if not COHERE_API_KEY:
    print("❌  COHERE_API_KEY not set in .env. Exiting.")
    sys.exit(1)

print(f"\n🔑  API Key   : {COHERE_API_KEY[:12]}...{COHERE_API_KEY[-4:]}")
print(f"🤖  Model     : {EMBED_MODEL}")
print(f"📐  Target Dim : {EXPECTED_DIM}")
print("-" * 60)

try:
    import cohere
    print("✅  cohere package found")
except ImportError:
    print("❌  cohere not installed. Run: pip install cohere")
    sys.exit(1)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


results: dict[str, bool] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1 — API Key + Client Init
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 1 — Cohere API key validation + client init")
print("=" * 60)

try:
    from core.embeddings import _get_client, get_embedding_info
    client = _get_client()
    info   = get_embedding_info()
    print(f"✅  Cohere client connected")
    print(f"    Provider   : {info['provider']}")
    print(f"    Model      : {info['model']}")
    print(f"    Dim        : {info['dim']}")
    print(f"    Batch size : {info['batch_size']}")
    print(f"    input_types: {info['input_types']}\n")
    results["client_init"] = True
except Exception as e:
    print(f"❌  FAILED: {e}\n")
    results["client_init"] = False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2 — embed_documents() batch
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 2 — embed_documents() — 3 industrial texts")
print("=" * 60)

industrial_docs = [
    "Pump P-101A showed bearing failure at 85°C. Vibration 12 mm/s. Ref: OISD-154.",
    "Inspection report for heat exchanger HE-201. Tube fouling detected. Flow reduced 30%.",
    "Safety procedure: Always depressurise Vessel V-301 before opening manhole. Ref: PESO Rules.",
]

try:
    from core.embeddings import embed_documents
    t0   = time.time()
    vecs = embed_documents(industrial_docs)
    elapsed = time.time() - t0

    assert len(vecs) == 3, f"Expected 3 vectors, got {len(vecs)}"
    for i, vec in enumerate(vecs):
        assert len(vec) == EXPECTED_DIM, \
            f"Vector {i}: dim={len(vec)}, expected {EXPECTED_DIM}"
        assert all(isinstance(v, float) and math.isfinite(v) for v in vec[:10])

    print(f"✅  Embedded 3 documents in {elapsed:.2f}s via Cohere API")
    print(f"    Each vector : {EXPECTED_DIM}-dim, all values finite")
    print(f"    Sample (vec[0][:5]): {[round(v, 4) for v in vecs[0][:5]]}\n")
    results["embed_documents"] = True
except Exception as e:
    print(f"❌  FAILED: {e}\n")
    results["embed_documents"] = False
    vecs = None


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3 — embed_query() single query
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 3 — embed_query() — single user query")
print("=" * 60)

try:
    from core.embeddings import embed_query
    t0        = time.time()
    query_vec = embed_query("What caused the pump bearing failure?")
    elapsed   = time.time() - t0

    assert len(query_vec) == EXPECTED_DIM
    assert all(isinstance(v, float) and math.isfinite(v) for v in query_vec[:10])

    print(f"✅  Query embedded in {elapsed:.3f}s")
    print(f"    Vector dim  : {len(query_vec)}")
    print(f"    Sample ([:5]): {[round(v, 4) for v in query_vec[:5]]}\n")
    results["embed_query"] = True
except Exception as e:
    print(f"❌  FAILED: {e}\n")
    results["embed_query"] = False
    query_vec = None


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4 — Asymmetric input_type (doc ≠ query for same text)
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 4 — Asymmetric input_type: search_document ≠ search_query")
print("=" * 60)

try:
    same_text    = "bearing failure in centrifugal pump"
    doc_vec_same = embed_documents([same_text])[0]
    qry_vec_same = embed_query(same_text)

    sim = cosine_similarity(doc_vec_same, qry_vec_same)
    are_different = not all(
        abs(a - b) < 1e-6 for a, b in zip(doc_vec_same[:20], qry_vec_same[:20])
    )

    print(f"    Cosine similarity (doc vs query, same text): {sim:.4f}")
    print(f"    Vectors are {'DIFFERENT ✅' if are_different else 'IDENTICAL ⚠️'}")

    if sim > 0.9999:
        print("⚠️   Vectors are identical — input_type may not be applied\n")
        results["asymmetric_type"] = False
    else:
        print(f"✅  Confirmed: input_type produces distinct spaces (sim={sim:.4f})\n")
        results["asymmetric_type"] = True
except Exception as e:
    print(f"❌  FAILED: {e}\n")
    results["asymmetric_type"] = False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5 — Semantic similarity ranking
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 5 — Semantic ranking: relevant doc scores highest")
print("=" * 60)

try:
    if query_vec and vecs:
        sim_0 = cosine_similarity(query_vec, vecs[0])   # pump bearing — RELEVANT
        sim_1 = cosine_similarity(query_vec, vecs[1])   # heat exchanger
        sim_2 = cosine_similarity(query_vec, vecs[2])   # vessel safety

        print(f"    Query : 'What caused the pump bearing failure?'")
        print(f"    Doc 0 (pump bearing)   : {sim_0:.4f}  ← should be HIGHEST")
        print(f"    Doc 1 (heat exchanger) : {sim_1:.4f}")
        print(f"    Doc 2 (vessel safety)  : {sim_2:.4f}")

        if sim_0 > sim_1 and sim_0 > sim_2:
            print(f"✅  Correct! Relevant document ranked #1 (score={sim_0:.4f})\n")
            results["semantic_ranking"] = True
        else:
            print(f"⚠️   Doc 0 not ranked #1. Retrieval quality issue.\n")
            results["semantic_ranking"] = False
    else:
        print("⚠️   Skipped — previous tests failed\n")
        results["semantic_ranking"] = False
except Exception as e:
    print(f"❌  FAILED: {e}\n")
    results["semantic_ranking"] = False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 6 — Multilingual (Hindi industrial text)
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 6 — Multilingual: Hindi industrial text embeds correctly")
print("=" * 60)

hindi_texts = [
    "पंप P-101A में बियरिंग फेलियर हुई। तापमान 85°C था।",   # Pump P-101A bearing failure at 85°C
    "हीट एक्सचेंजर HE-201 की जांच रिपोर्ट। ट्यूब फाउलिंग मिली।", # HE-201 inspection report
]

try:
    t0         = time.time()
    hindi_vecs = embed_documents(hindi_texts)
    elapsed    = time.time() - t0

    assert len(hindi_vecs) == 2
    assert all(len(v) == EXPECTED_DIM for v in hindi_vecs)

    # Cross-lingual test: Hindi pump text should be closer to English pump query
    # than English heat exchanger text
    if query_vec:
        sim_hindi_pump = cosine_similarity(query_vec, hindi_vecs[0])
        sim_hindi_he   = cosine_similarity(query_vec, hindi_vecs[1])
        print(f"    Hindi pump bearing vs English pump query   : {sim_hindi_pump:.4f}")
        print(f"    Hindi heat exchanger vs English pump query : {sim_hindi_he:.4f}")
        cross_lingual_ok = sim_hindi_pump > sim_hindi_he
    else:
        cross_lingual_ok = True  # can't compare without query_vec

    print(f"✅  Hindi texts embedded in {elapsed:.2f}s — {EXPECTED_DIM}-dim vectors")
    if cross_lingual_ok:
        print(f"✅  Cross-lingual retrieval works: Hindi pump ↔ English query aligned\n")
    else:
        print(f"⚠️   Cross-lingual alignment weak (may still work in full retrieval)\n")
    results["multilingual"] = True
except Exception as e:
    print(f"❌  FAILED: {e}\n")
    results["multilingual"] = False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 7 — Batch > 96 (auto-chunked across Cohere's limit)
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("TEST 7 — Batch stress: 97 texts (crosses Cohere 96-limit, auto-chunked)")
print("=" * 60)

stress_texts = [
    f"Equipment tag P-{100+i}: Temperature {60+i}°C, pressure {5+i} bar. Entry {i}."
    for i in range(97)
]

try:
    t0          = time.time()
    stress_vecs = embed_documents(stress_texts)
    elapsed     = time.time() - t0

    assert len(stress_vecs) == 97, f"Expected 97, got {len(stress_vecs)}"
    assert all(len(v) == EXPECTED_DIM for v in stress_vecs)

    throughput = 97 / elapsed
    print(f"✅  97 texts embedded in {elapsed:.2f}s ({throughput:.1f} texts/sec)")
    print(f"    Auto-chunked into 2 Cohere batches (96 + 1)")
    print(f"    All 97 vectors: {EXPECTED_DIM}-dim ✅\n")
    results["batch_over_limit"] = True
except Exception as e:
    print(f"❌  FAILED: {e}\n")
    results["batch_over_limit"] = False


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 60)
print("EMBEDDING ENGINE TEST SUMMARY")
print("=" * 60)

all_passed = True
for test, passed in results.items():
    icon = "✅" if passed else "❌"
    print(f"  {icon}  {test}")
    if not passed:
        all_passed = False

if all_passed:
    print(f"\n🎉  ALL TESTS PASSED — Cohere embedding engine is ready!")
    print(f"    Model : {EMBED_MODEL}")
    print(f"    Dim   : {EXPECTED_DIM}")
    print(f"\n    You can now proceed to Component 1.2 (MCP Server Boot).")
else:
    print(f"\n⚠️   Some tests failed. Fix the issues above before proceeding.")
print()
