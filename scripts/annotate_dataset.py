import os
import sys
import json
import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env

# Add mcp-server directory to sys.path
mcp_server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'mcp-server'))
sys.path.append(mcp_server_path)

import fitz  # PyMuPDF
from core import llm_client

DATASET_DIR = Path("NER_dataset")
OUTPUT_FILE = DATASET_DIR / "training_data.jsonl"
RATE_LIMIT_DELAY = 1.5  # 40 requests/min = 1.5s between requests

PROMPT_TEMPLATE = """Analyze the following text from an industrial manual.
Extract named entities exactly as they appear in the text for the following categories:
- "Equipment Tag" (e.g. P-101, V-200, FIC-304)
- "Process Parameter" (e.g. 15 bar, 45°C, 300 GPM, 100 rpm)
- "Regulatory Reference" (e.g. OISD-154, API 610, IS:2825)
- "Failure Mode" (e.g. bearing failure, leak, corrosion, high vibration)
- "Person" (names of individuals)
- "Date" (dates, times, timestamps)
- "Chemical" (e.g. Water, H2S, Oil, Steam)

Ensure the extracted "text" is an EXACT substring of the provided text (case-sensitive).

Text to analyze:
----------------
{text}
----------------

Return ONLY a JSON list of objects. Example:
[
  {{"label": "Equipment Tag", "text": "P-101"}},
  {{"label": "Process Parameter", "text": "15 bar"}}
]
If no entities are found, return []."""

def chunk_text(text, max_words=200):
    """Split text into manageable chunks for the LLM."""
    words = text.split()
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]

async def annotate_chunk(chunk_text: str) -> list:
    """Call Mistral LLM to extract entities."""
    prompt = PROMPT_TEMPLATE.format(text=chunk_text)
    
    start_time = time.time()
    try:
        response = await llm_client.json_chat(prompt, temperature=0.1)
    except Exception as e:
        print(f"LLM Error: {e}")
        response = []
    
    elapsed = time.time() - start_time
    if elapsed < RATE_LIMIT_DELAY:
        await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
        
    return response if isinstance(response, list) else []

def find_spans(text: str, entities: list) -> list:
    """Map extracted text strings to [start, end] character indices."""
    spans = []
    for ent in entities:
        ent_text = ent.get("text", "")
        label = ent.get("label", "")
        if not ent_text or not label:
            continue
            
        start_idx = text.find(ent_text)
        if start_idx != -1:
            end_idx = start_idx + len(ent_text)
            spans.append([start_idx, end_idx, label, ent_text])
            
    return spans

async def main():
    print(f"Starting dataset annotation. Output will be saved to {OUTPUT_FILE}")
    if not DATASET_DIR.exists():
        print(f"Directory {DATASET_DIR} not found.")
        return

    # Clear output file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        pass

    pdf_files = list(DATASET_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files.")

    total_chunks_processed = 0
    total_entities_found = 0

    for pdf_path in pdf_files:
        print(f"\nProcessing {pdf_path.name}...")
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            print(f"Failed to open PDF {pdf_path.name}: {e}")
            continue

        for page_num, page in enumerate(doc):
            text = page.get_text("text").strip()
            if not text:
                continue
                
            chunks = chunk_text(text, max_words=200)
            
            for chunk_idx, chunk in enumerate(chunks):
                if len(chunk) < 20: # Skip very small chunks
                    continue
                    
                print(f"  - Annotating Page {page_num+1}, Chunk {chunk_idx+1}/{len(chunks)}...", end="", flush=True)
                
                llm_entities = await annotate_chunk(chunk)
                spans = find_spans(chunk, llm_entities)
                
                if not spans:
                    print(" Found 0 entities.")
                    continue
                
                gliner_record = {
                    "text": chunk,
                    "label": spans
                }
                
                # Append to JSONL
                with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(gliner_record) + "\n")
                
                print(f" Found {len(spans)} entities.")
                total_chunks_processed += 1
                total_entities_found += len(spans)
                
    print(f"\nAnnotation complete! Processed {total_chunks_processed} chunks and found {total_entities_found} entities.")

if __name__ == "__main__":
    asyncio.run(main())
