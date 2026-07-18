import asyncio
import sys
import time
from pathlib import Path

# Add the mcp-server directory to sys.path so we can import tools naturally
project_root = Path(__file__).resolve().parent.parent
mcp_server_path = project_root / "mcp-server"
sys.path.insert(0, str(mcp_server_path))

try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

from tools.ingestion.excel_tool import ingest_excel
from tools.ingestion.pdf_tool import ingest_pdf

async def main():
    inbox_dir = project_root / "data" / "watch_inbox"
    
    csv_file = inbox_dir / "erp_workorders.csv"
    pdf_file = inbox_dir / "QMS-MASTER-MANUAL.pdf"
    
    print("=== Starting Manual Ingestion ===")
    
    if csv_file.exists():
        print(f"\n[1] Ingesting Excel/CSV Data: {csv_file.name}")
        try:
            res = await ingest_excel(str(csv_file))
            print(f"Result: {res}")
        except Exception as e:
            print(f"Error during Excel ingestion: {e}")
    else:
        print(f"\n[1] File not found: {csv_file}")
        
    print("\n[PAUSE] Sleeping for 65 seconds to avoid Cohere API rate limits (100k tokens/min)...")
    for i in range(65, 0, -5):
        print(f"... {i} seconds remaining")
        await asyncio.sleep(5)
        
    if pdf_file.exists():
        print(f"\n[2] Ingesting PDF Document: {pdf_file.name}")
        try:
            res = await ingest_pdf(str(pdf_file))
            print(f"Result: {res}")
        except Exception as e:
            print(f"Error during PDF ingestion: {e}")
    else:
        print(f"\n[2] File not found: {pdf_file}")
        
    print("\n=== Ingestion Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
