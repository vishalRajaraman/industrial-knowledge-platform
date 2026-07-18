import os
import sys
import asyncio
import pandas as pd
from pathlib import Path

# Add project root to sys.path to import from mcp-server
project_root = Path(__file__).resolve().parent.parent
# Python imports use hyphens directly if module name has it, wait! python packages cannot have hyphens.
# Python imports from a folder called `mcp-server` won't work out of the box because of the hyphen.
# I need to dynamically import it or use importlib.
sys.path.append(str(project_root))

import importlib.util
mcp_server_path = project_root / "mcp-server"

def import_module_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

qms_connector = import_module_from_path("qms_connector", mcp_server_path / "tools" / "ingestion" / "qms_connector.py")
erp_connector = import_module_from_path("erp_connector", mcp_server_path / "tools" / "ingestion" / "erp_connector.py")

async def main():
    print("Generating QMS and ERP data...")
    inbox_dir = project_root / "data" / "watch_inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Generate ERP data first to get the actual materials used
    erp_res = await erp_connector.sync_erp_workorders_logic(limit=100)
    materials = []
    
    if erp_res.get("status") == "success":
        data = erp_res.get("data", [])
        if data:
            df = pd.DataFrame(data)
            csv_path = inbox_dir / "erp_workorders.csv"
            df.to_csv(csv_path, index=False)
            print(f"[OK] Generated {csv_path}")
            
            # Extract unique materials for QMS
            seen = set()
            for row in data:
                mat_id = row.get("equipment_tag")
                mat_name = row.get("equipment_name")
                if mat_id and mat_id not in seen:
                    seen.add(mat_id)
                    materials.append({"id": mat_id, "name": mat_name})
    else:
        print(f"[ERROR] ERP Error: {erp_res}")

    # 2. Generate QMS using the materials from ERP
    qms_res = await qms_connector.sync_qms_documents_logic(base_url="mock", materials=materials)
    if qms_res.get("status") == "success":
        md_file_path = inbox_dir / "QMS-MASTER-MANUAL.md"
        pdf_file_path = inbox_dir / "QMS-MASTER-MANUAL.pdf"
        
        # Convert simple markdown to PDF to be compatible with watcher
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            c = canvas.Canvas(str(pdf_file_path), pagesize=letter)
            width, height = letter
            y = height - 50
            
            with open(md_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    c.drawString(50, y, line.strip())
                    y -= 15
                    if y < 50:
                        c.showPage()
                        y = height - 50
            c.save()
            print(f"[OK] Generated {pdf_file_path}")
            
            # Remove the .md file as watcher doesn't support it
            if md_file_path.exists():
                md_file_path.unlink()
                
        except ImportError:
            print("[ERROR] Reportlab not installed. Please run: pip install reportlab")
    else:
        print(f"[ERROR] QMS Error: {qms_res}")

if __name__ == "__main__":
    asyncio.run(main())
