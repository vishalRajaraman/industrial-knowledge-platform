"""
ERP Connector Tool
Simulates an API connection to an ERP system (e.g. SAP/Maximo) by querying local CSV datasets.
Uses pandas to join multiple SAP tables (ekko, ekpo, makt, lfa1) to produce a detailed payload.
"""
import os
import logging
from pathlib import Path
import pandas as pd
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("ikp.ingest.erp_connector")

def register(mcp: FastMCP):
    @mcp.tool()
    async def sync_erp_workorders(system: str = "SAP", endpoint: str = "/api/workorders", limit: int = 50) -> dict:
        """
        Simulate fetching detailed maintenance work orders from an ERP system (like SAP or Maximo).
        This tool uses pandas to join ekko (Orders), ekpo (Items), makt (Material Names), 
        and lfa1 (Vendor Names) to produce a rich Knowledge Graph node.
        
        Args:
            system: ERP system name (e.g. "SAP", "Maximo")
            endpoint: API endpoint being mocked
            limit: Maximum number of records to return
        """
        dataset_path_env = os.getenv("ERP_DATASET_PATH")
        if dataset_path_env:
            dataset_path = Path(dataset_path_env)
        else:
            # Fallback for local development
            dataset_path = Path(__file__).resolve().parent.parent.parent.parent / "erp_dataset"
        
        # Define paths
        ekko_file = dataset_path / "ekko.csv"
        ekpo_file = dataset_path / "ekpo.csv"
        makt_file = dataset_path / "makt.csv"
        lfa1_file = dataset_path / "lfa1.csv"
        
        if not ekko_file.exists():
            return {"status": "error", "message": f"Dataset file not found at {ekko_file}"}

        try:
            # 1. Read Order Headers (ekko) - limit to reduce processing
            # We map ebeln -> work_order_id
            ekko_df = pd.read_csv(ekko_file, usecols=["ebeln", "lifnr", "statu", "ernam", "bsart"], nrows=limit, dtype=str)
            
            # 2. Read Order Items (ekpo) - to get material (matnr)
            ekpo_df = pd.read_csv(ekpo_file, usecols=["ebeln", "matnr"], dtype=str)
            
            # 3. Read Material Descriptions (makt) - to get material name (maktx)
            makt_df = pd.read_csv(makt_file, usecols=["matnr", "maktx"], dtype=str)
            # Drop duplicates (e.g. if multiple languages exist for the same material)
            makt_df = makt_df.drop_duplicates(subset=["matnr"])
            
            # 4. Read Vendor Master (lfa1) - to get vendor name (name1)
            lfa1_df = pd.read_csv(lfa1_file, usecols=["lifnr", "name1"], dtype=str)
            lfa1_df = lfa1_df.drop_duplicates(subset=["lifnr"])

            # Merge DataFrames
            df = pd.merge(ekko_df, ekpo_df, on="ebeln", how="left")
            df = pd.merge(df, makt_df, on="matnr", how="left")
            df = pd.merge(df, lfa1_df, on="lifnr", how="left")

            # Fill NaNs with empty string
            df = df.fillna("")

            # Build JSON output
            work_orders = []
            for _, row in df.iterrows():
                work_order_id = row.get("ebeln", "")
                equipment_tag = row.get("matnr", "")
                equipment_name = row.get("maktx", "")
                vendor_name = row.get("name1", "")
                
                status = row.get("statu", "OPEN")
                if not status:
                    status = "OPEN"
                
                ernam = row.get("ernam", "")
                bsart = row.get("bsart", "")
                description = f"Purchasing Doc created by {ernam}. Type: {bsart}"
                
                work_orders.append({
                    "work_order_id": work_order_id,
                    "equipment_tag": equipment_tag,
                    "equipment_name": equipment_name,
                    "vendor_name": vendor_name,
                    "status": status,
                    "description": description
                })
                    
            return {
                "status": "success",
                "system": system,
                "endpoint": endpoint,
                "count": len(work_orders),
                "data": work_orders
            }
        except Exception as e:
            logger.error(f"Failed to sync ERP workorders: {e}")
            return {"status": "error", "message": str(e)}
