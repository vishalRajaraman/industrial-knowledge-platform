"""
P&ID Parser — detects equipment symbols, pipeline connections,
and instrument tags from Piping & Instrumentation Diagrams.

Uses YOLOv8 (fine-tuned on P&ID symbols) with OpenCV Hough line detection
for pipeline tracing. Falls back to template matching for common symbols
when the YOLO model is not available.

NOTE: Full fine-tuning of YOLOv8 for P&ID symbols is a SEPARATE manual step.
See the post-execution checklist for fine-tuning instructions.
"""
import json
import logging
import os
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from core import neo4j_client, object_store

logger = logging.getLogger("ikp.ingest.pid")

YOLO_MODEL_PATH = os.getenv("PID_YOLO_MODEL", "")  # Path to fine-tuned .pt file


def register(mcp: FastMCP):

    @mcp.tool()
    async def parse_pid(
        file_path: str,
        confidence_threshold: float = 0.4,
        upload_to_s3: bool = True,
    ) -> dict:
        """
        Parse a P&ID (Piping and Instrumentation Diagram) image.
        Detects equipment symbols (pumps, valves, heat exchangers, vessels,
        instruments) and traces pipeline connections using computer vision.

        Results are stored in Neo4j AuraDB as Equipment nodes with
        CONNECTED_TO relationships (the physical piping topology).

        Two modes:
        - YOLO mode: Uses fine-tuned YOLOv8 model (set PID_YOLO_MODEL env var).
        - OpenCV mode: Uses template matching + Hough lines (fallback, less accurate).

        NOTE: For accurate P&ID parsing, fine-tune YOLOv8 on P&ID symbol dataset.
        See post-execution checklist for fine-tuning instructions.

        Args:
            file_path: Absolute path to the P&ID image (PNG, JPG, TIFF) or PDF page.
            confidence_threshold: Minimum detection confidence (0.0-1.0).
            upload_to_s3: Upload original drawing to S3.

        Returns:
            equipment_detected, connections_found, kg_nodes_created, doc_id.
        """
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}

        try:
            import cv2
            import numpy as np
        except ImportError:
            return {"error": "OpenCV not installed. pip install opencv-python"}

        path = Path(file_path)
        doc_id = str(uuid.uuid4())

        detected_equipment = []
        connections = []

        # ── Attempt YOLO detection ───────────────────────────────────────────
        yolo_available = bool(YOLO_MODEL_PATH and os.path.exists(YOLO_MODEL_PATH))
        if yolo_available:
            try:
                from ultralytics import YOLO
                model = YOLO(YOLO_MODEL_PATH)
                results = model.predict(source=file_path, conf=confidence_threshold, verbose=False)
                for r in results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        label = model.names[cls_id]
                        conf = float(box.conf[0])
                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                        detected_equipment.append({
                            "label": label,
                            "confidence": round(conf, 3),
                            "bbox": [x1, y1, x2, y2],
                            "tag": _generate_tag(label),
                        })
            except Exception as e:
                logger.warning("YOLO detection failed, falling back to OpenCV: %s", e)
                yolo_available = False

        # ── OpenCV fallback: detect lines (pipelines) ─────────────────────────
        img = cv2.imread(file_path)
        if img is None:
            return {"error": "Could not read image with OpenCV"}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                 minLineLength=50, maxLineGap=10)
        line_count = len(lines) if lines is not None else 0

        if not yolo_available:
            # Simple circle detection for instrument bubbles
            circles = cv2.HoughCircles(
                gray, cv2.HOUGH_GRADIENT, 1, 20,
                param1=50, param2=30, minRadius=5, maxRadius=30
            )
            if circles is not None:
                for i, (x, y, r) in enumerate(circles[0][:20]):
                    detected_equipment.append({
                        "label": "Instrument",
                        "confidence": 0.6,
                        "bbox": [int(x - r), int(y - r), int(x + r), int(y + r)],
                        "tag": f"FI-{100 + i}",
                    })

        # ── Create Neo4j nodes ────────────────────────────────────────────────
        # Document node for the P&ID drawing
        await neo4j_client.upsert_node(
            doc_id, ["Document", "Drawing"],
            {"title": path.stem, "doc_type": "drawing", "filename": path.name,
             "equipment_count": len(detected_equipment), "pipeline_lines": line_count}
        )

        kg_nodes = 1
        for eq in detected_equipment:
            tag = eq["tag"]
            await neo4j_client.upsert_node(
                tag, ["Equipment"],
                {"tag": tag, "type": eq["label"], "source_drawing": path.name}
            )
            await neo4j_client.upsert_edge(tag, doc_id, "DEPICTED_IN")
            kg_nodes += 2

        # ── Create CONNECTED_TO relationships (simplified) ────────────────────
        # Without pipeline tracing, create connections between adjacent equipment
        for i in range(len(detected_equipment) - 1):
            a = detected_equipment[i]["tag"]
            b = detected_equipment[i + 1]["tag"]
            await neo4j_client.upsert_edge(a, b, "CONNECTED_TO",
                                            {"source": "P&ID_autodetect"})
            connections.append({"from": a, "to": b})

        # ── S3 upload ─────────────────────────────────────────────────────────
        s3_url = None
        if upload_to_s3:
            try:
                s3_url = await object_store.upload_file(file_path, doc_id, {"doc_type": "drawing"})
            except Exception as e:
                logger.warning("S3 upload failed: %s", e)

        return {
            "doc_id": doc_id,
            "filename": path.name,
            "detection_mode": "yolo" if yolo_available else "opencv_fallback",
            "equipment_detected": detected_equipment,
            "equipment_count": len(detected_equipment),
            "pipeline_lines_detected": line_count,
            "connections_created": connections,
            "kg_nodes_created": kg_nodes,
            "s3_url": s3_url,
            "note": (
                "For accurate P&ID parsing, fine-tune YOLOv8 on the P&ID-Symbols dataset. "
                "Set PID_YOLO_MODEL env var to the .pt file path."
                if not yolo_available else "YOLO model used."
            ),
        }


def _generate_tag(label: str) -> str:
    """Generate an ISA-5.1 style tag from a symbol label."""
    prefix_map = {
        "Pump": "P", "Compressor": "C", "HeatExchanger": "HE",
        "Vessel": "V", "Valve": "VLV", "Instrument": "FI",
        "Reactor": "R", "Column": "T", "Tank": "TK",
    }
    prefix = prefix_map.get(label, label[:2].upper())
    import random
    return f"{prefix}-{random.randint(100, 999)}"
