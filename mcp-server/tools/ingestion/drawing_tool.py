import asyncio
import base64
import json
import logging
import os
import uuid
from pathlib import Path
import re

import cv2
import requests
from mcp.server.fastmcp import FastMCP

from core import neo4j_client

logger = logging.getLogger("ikp.ingest.drawing")

# Strong references for background tasks so they aren't garbage collected
_background_tasks = set()

def register(mcp: FastMCP):
    @mcp.tool()
    async def digitize_drawing(
        file_path: str,
        drawing_type: str = "general"
    ) -> dict:
        """
        Digitize a general engineering drawing (layout, floor plan, isometric).
        Extracts spatial regions (e.g. rooms, major equipment zones) and their 
        relationships using the minimax-m3 Vision model on NVIDIA NIM.

        Args:
            file_path: Absolute path to the image file (png, jpeg, etc.).
            drawing_type: Type of drawing (e.g. "floor_plan", "equipment_layout").
        """
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        doc_id = str(uuid.uuid4())
        logger.info("Digitizing %s drawing: %s (doc_id=%s)", drawing_type, path.name, doc_id)

        try:
            with open(path, "rb") as f:
                img_bytes = f.read()
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        except Exception as e:
            logger.error("Failed to read image %s: %s", path.name, e)
            return {"error": f"Failed to read image: {e}"}

        # ── Call Groq Vision API ──────────────────────────────────────────────
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return {"error": "GROQ_API_KEY is not set in environment."}

        invoke_url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        # The strict prompt for extracting regions
        prompt_text = (
            "Extract all major regions/rooms/zones with their bounding boxes "
            "(format [ymin, xmin, ymax, xmax] normalized 0.0 to 1.0) and spatial "
            "relationship to the largest region in the image in strict JSON format. "
            "JSON should be an array of objects with keys: 'label', 'bbox', "
            "and 'spatial_relationship_to_largest'."
        )

        payload = {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                    ]
                }
            ],
            "temperature": 0.2,
            "top_p": 0.95,
            "max_tokens": 2048,
            "stream": False
        }

        logger.info("Sending request to Groq llama-3.2-90b-vision-preview...")
        try:
            # We must use asyncio.to_thread because requests.post is blocking
            response = await asyncio.to_thread(
                requests.post, invoke_url, headers=headers, json=payload, timeout=180
            )
            response.raise_for_status()
            
            resp_json = response.json()
            content = resp_json["choices"][0]["message"]["content"]
            
            # Clean up the markdown formatting if the model wrapped it in ```json
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
            if match:
                content = match.group(1)
            else:
                content = content.strip()
            
            try:
                regions = json.loads(content.strip())
            except json.JSONDecodeError as e:
                logger.error("Failed to parse JSON. Raw content: %s", content)
                raise e
        except Exception as e:
            logger.error("Vision API failed: %s", e)
            if hasattr(e, 'response') and e.response is not None:
                logger.error("Response: %s", e.response.text)
            return {"error": f"Vision API failed: {e}"}

        # ── Draw Bounding Boxes and Save Annotated Image ──────────────────────
        annotated_img_path = str(path.parent / f"{path.stem}_annotated{path.suffix}")
        
        # Load image via cv2 to draw
        img = cv2.imread(str(path))
        if img is None:
            return {"error": "Failed to decode image with cv2 for annotation"}
            
        h, w, _ = img.shape
        
        extracted_data = []

        for region in regions:
            label = region.get("label", "Unknown")
            rel = region.get("spatial_relationship_to_largest", "")
            bbox = region.get("bbox", [0, 0, 0, 0])
            
            if len(bbox) == 4:
                # Convert normalized [ymin, xmin, ymax, xmax] to pixel coordinates
                ymin, xmin, ymax, xmax = bbox
                pt1 = (int(xmin * w), int(ymin * h))
                pt2 = (int(xmax * w), int(ymax * h))
                
                cv2.rectangle(img, pt1, pt2, (255, 0, 0), 2)
                cv2.putText(img, label, (pt1[0], max(pt1[1] - 5, 10)), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
                
                extracted_data.append({
                    "label": label,
                    "bbox_px": [pt1[0], pt1[1], pt2[0], pt2[1]],
                    "bbox_norm": bbox,
                    "relationship": rel
                })

        cv2.imwrite(annotated_img_path, img)

        # ── Write to Neo4j as a background task ───────────────────────────────
        async def _background_persist():
            try:
                # Document node
                await neo4j_client.upsert_node(
                    doc_id, ["Document", "Drawing"],
                    {
                        "title": path.stem, 
                        "doc_type": drawing_type, 
                        "filename": path.name,
                        "region_count": len(extracted_data)
                    }
                )
                
                def get_spatial_rel(b1, b2):
                    y1_min, x1_min, y1_max, x1_max = b1
                    y2_min, x2_min, y2_max, x2_max = b2
                    c1_x, c1_y = (x1_min + x1_max) / 2, (y1_min + y1_max) / 2
                    c2_x, c2_y = (x2_min + x2_max) / 2, (y2_min + y2_max) / 2
                    
                    if x1_min >= x2_min and x1_max <= x2_max and y1_min >= y2_min and y1_max <= y2_max:
                        return "INSIDE"
                    if x2_min >= x1_min and x2_max <= x1_max and y2_min >= y1_min and y2_max <= y1_max:
                        return "CONTAINS"
                        
                    dx, dy = c1_x - c2_x, c1_y - c2_y
                    if abs(dx) > abs(dy):
                        return "RIGHT_OF" if dx > 0 else "LEFT_OF"
                    else:
                        return "BELOW" if dy > 0 else "ABOVE"

                # First create all nodes
                for i, reg in enumerate(extracted_data):
                    region_id = f"{doc_id}_region_{i}"
                    await neo4j_client.upsert_node(
                        region_id, ["DrawingRegion"],
                        {
                            "label": reg["label"],
                            "source_drawing": path.name,
                            "bbox": str(reg["bbox_norm"])
                        }
                    )
                    await neo4j_client.upsert_edge(region_id, doc_id, "DEPICTED_IN")
                    
                # Then create edges between all pairs
                for i, reg1 in enumerate(extracted_data):
                    region1_id = f"{doc_id}_region_{i}"
                    for j, reg2 in enumerate(extracted_data):
                        if i == j:
                            continue
                        
                        rel = get_spatial_rel(reg1["bbox_norm"], reg2["bbox_norm"])
                        edge_type = f"SPATIALLY_RELATED_TO_{rel}"
                        
                        await neo4j_client.upsert_edge(
                            region1_id, f"{doc_id}_region_{j}", edge_type,
                            {"computed": True}
                        )
                        
                logger.info("Neo4j: wrote %d regions for doc_id=%s", len(extracted_data), doc_id)
            except Exception as e:
                logger.error("Neo4j background write failed: %s", e)

        # Fire-and-forget
        task = asyncio.create_task(_background_persist())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        # ── Return result instantly ────────────────────────────────────────────
        return {
            "message": "Drawing digitized successfully",
            "regions_detected": len(extracted_data),
            "drawing_type": drawing_type,
            "annotated_image_path": annotated_img_path,
            "neo4j_status": "writing_in_background",
            "doc_id": doc_id,
            "extracted_data": extracted_data
        }
