"""
QMS Connector Tool
Simulates a connection to a Quality Management System (QMS) to pull quality manuals, 
inspection records, and compliance standards.
"""
import os
import json
import logging
import urllib.request
import shutil
import pandas as pd
from pathlib import Path
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("ikp.ingest.qms_connector")

def register(mcp: FastMCP):
    @mcp.tool()
    async def sync_qms_documents(qms_type: str = "MockQMS", base_url: str = "mock", token: str = "dummy_token") -> dict:
        """
        Fetch document metadata and download files from a Quality Management System.
        Downloads files to the local /data/watch_inbox folder so they can be ingested into the Knowledge Graph.
        
        Args:
            qms_type: The type of QMS (e.g. 'Qualio', 'MasterControl', 'ETQ', or 'MockQMS')
            base_url: The REST API base URL. Use 'mock' to generate local mock files, 
                      or provide a real URL to download a file from the internet.
            token: API authentication token.
        """
        # Determine the project root and the watch inbox directory
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        inbox_dir = project_root / "data" / "watch_inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        
        downloaded_files = []
        metadata_list = []
        
        try:
            if base_url == "mock":
                # Create a massive mock file based on actual ERP dataset values
                mock_file_name = "QMS-MASTER-MANUAL.md"
                mock_file_path = inbox_dir / mock_file_name
                
                dataset_path_env = os.getenv("ERP_DATASET_PATH")
                if dataset_path_env:
                    dataset_path = Path(dataset_path_env)
                else:
                    dataset_path = project_root / "erp_dataset"
                
                makt_file = dataset_path / "makt.csv"
                
                materials = []
                if makt_file.exists():
                    try:
                        # Read the first 50 materials to keep file size reasonable
                        makt_df = pd.read_csv(makt_file, usecols=["matnr", "maktx"], dtype=str, nrows=50)
                        for _, row in makt_df.iterrows():
                            materials.append({"id": row["matnr"], "name": str(row["maktx"]).strip()})
                    except Exception as e:
                        logger.warning(f"Could not read makt.csv: {e}")
                
                # Fallback if no materials found
                if not materials:
                    materials = [{"id": "000000008360373865", "name": "BBQ chips"}]
                
                with open(mock_file_path, "w", encoding="utf-8") as f:
                    f.write("# MASTER QUALITY MANUAL & INSPECTION STANDARDS\n\n")
                    f.write("Document ID: QMS-MASTER-001\n")
                    f.write("Status: APPROVED\n\n")
                    f.write("This document outlines the strict quality control parameters, inspection routines, and compliance standards for all manufactured and procured materials.\n\n")
                    
                    for mat in materials:
                        f.write(f"## Material: {mat['name']} (ID: {mat['id']})\n")
                        f.write("### 1. Scope & Compliance\n")
                        f.write(f"This section details the critical quality standards required for {mat['name']} to meet ISO 9001 compliance.\n\n")
                        f.write("### 2. Inspection Parameters\n")
                        f.write("- **Visual Inspection**: Ensure no physical defects, discoloration, or foreign contaminants.\n")
                        f.write("- **Dimensional Tolerance**: Must adhere to strict standard specifications +/- 0.05mm.\n")
                        f.write("- **Stress Testing**: Perform sampling at 1% of the batch size for ultimate tensile strength and durability.\n")
                        f.write("- **Storage**: Must be kept in a climate-controlled environment to prevent degradation.\n\n")
                        f.write("---\n\n")
                    
                downloaded_files.append(str(mock_file_path))
                metadata_list.append({
                    "document_id": "QMS-MASTER-001",
                    "title": "Master Quality Manual",
                    "status": "APPROVED",
                    "file_name": mock_file_name,
                    "materials_covered": len(materials)
                })
                
            elif base_url.startswith("http"):
                # Real download mode
                # E.g. base_url could be the direct URL to a PDF compliance standard
                file_name = base_url.split("/")[-1]
                if not file_name:
                    file_name = "downloaded_compliance_standard.pdf"
                
                download_path = inbox_dir / file_name
                
                req = urllib.request.Request(base_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(download_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
                    
                downloaded_files.append(str(download_path))
                metadata_list.append({
                    "document_id": f"EXTERNAL-{file_name}",
                    "title": f"External Standard: {file_name}",
                    "status": "IMPORTED",
                    "file_name": file_name,
                    "source_url": base_url
                })
                
            else:
                return {"status": "error", "message": "Invalid base_url. Use 'mock' or a valid 'http' URL."}
                
            return {
                "status": "success",
                "qms_type": qms_type,
                "downloaded_files": downloaded_files,
                "metadata": metadata_list
            }
            
        except Exception as e:
            logger.error(f"Failed to sync QMS documents: {e}")
            return {"status": "error", "message": str(e)}
