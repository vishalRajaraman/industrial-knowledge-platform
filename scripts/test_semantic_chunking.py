import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.join(os.getcwd(), 'mcp-server'))
load_dotenv()

from tools.knowledge.chunker_tool import _chunk_text

sample_text = """
The centrifugal pump P-101A is critical for the main cooling loop. Regular maintenance involves checking the seal oil pressure and ensuring the vibration levels do not exceed 0.15 in/sec. If vibration is high, immediate shutdown is required.

In unrelated news, the cafeteria will be closed on Friday for renovations. All employees are advised to use the secondary break room located in building C. New coffee machines will be installed.

Back to safety protocols, all operators must wear Class 2 PPE when entering the compressor area. Ear protection is mandatory. Failure to comply will result in disciplinary action according to OISD standards.
"""

def test():
    print("Running Semantic Chunker test...\n")
    try:
        chunks = _chunk_text(sample_text, doc_id="test-doc-123", doc_type="general")
        print(f"Total chunks generated: {len(chunks)}\n")
        for chunk in chunks:
            print(f"--- Chunk {chunk['chunk_index']} ({chunk['char_length']} chars) ---")
            print(chunk['text'])
            print("-----------------------------------------------------------\n")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
