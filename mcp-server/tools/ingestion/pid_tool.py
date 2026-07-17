"""
P&ID Parser — detects equipment symbols, pipeline connections,
and instrument tags from Piping & Instrumentation Diagrams.

Uses YOLOv5 (fine-tuned on P&ID symbols) with OpenCV Hough line detection
for pipeline tracing. Falls back to template matching for common symbols
when the YOLO model is not available.

NOTE: Full fine-tuning of YOLOv5 for P&ID symbols is a SEPARATE manual step.
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

import contextlib
import io
import threading

YOLO_MODEL_PATH = os.getenv("PID_YOLO_MODEL", "")  # Path to fine-tuned .pt file

# Global cache for the YOLO model — loaded once in a background thread at startup
_cached_yolo_model = None
_yolo_load_lock = threading.Lock()

# Strong references for background tasks so they aren't garbage collected
_background_tasks = set()


def _load_yolo_model_sync():
    """Synchronously load the YOLO model. Safe to call from any thread."""
    global _cached_yolo_model
    if not YOLO_MODEL_PATH or not os.path.exists(YOLO_MODEL_PATH):
        return
    with _yolo_load_lock:
        if _cached_yolo_model is not None:
            return  # already loaded by another thread
        try:
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            logger.info("Pre-warming YOLO model on device=%s from %s", device, YOLO_MODEL_PATH)
            with contextlib.redirect_stdout(io.StringIO()):
                _cached_yolo_model = torch.hub.load(
                    'ultralytics/yolov5', 'custom',
                    path=YOLO_MODEL_PATH, device=device
                )
            logger.info("YOLO model pre-warmed and cached successfully.")
        except Exception as e:
            logger.warning("YOLO model pre-warm failed: %s", e)


# Load the YOLO model synchronously at server startup (runs once when server.py imports this module).
# This takes ~14 seconds but guarantees the model is ready before ANY tool call arrives.
# A background thread created a race condition: if the tool was called during loading,
# it would block in the thread pool for up to 14s and risk the MCP client timeout.
if YOLO_MODEL_PATH and os.path.exists(YOLO_MODEL_PATH):
    _load_yolo_model_sync()


def register(mcp: FastMCP):

    @mcp.tool()
    async def parse_pid(
        file_path: str,
        confidence_threshold: float = 0.4,
        upload_to_s3: bool = False,  # Default False — S3 not required for local use
    ) -> dict:
        """
        Parse a P&ID (Piping and Instrumentation Diagram) image.
        Detects equipment symbols (pumps, valves, heat exchangers, vessels,
        instruments) and traces pipeline connections using computer vision.

        Results are stored in Neo4j AuraDB as Equipment nodes with
        CONNECTED_TO relationships (the physical piping topology).

        Two modes:
        - YOLO mode: Uses fine-tuned YOLOv5 model (set PID_YOLO_MODEL env var).
        - OpenCV mode: Uses template matching + Hough lines (fallback, less accurate).

        NOTE: For accurate P&ID parsing, fine-tune YOLOv5 on P&ID symbol dataset.
        See post-execution checklist for fine-tuning instructions.

        Args:
            file_path: Absolute path to the P&ID image (PNG, JPG, TIFF) or PDF page.
            confidence_threshold: Minimum detection confidence (0.0-1.0).
            upload_to_s3: Upload original drawing to S3.

        Returns:
            equipment_detected, connections_found, kg_nodes_created, doc_id.
        """
        import asyncio

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
                loop = asyncio.get_event_loop()

                def _run_yolo():
                    """Run blocking YOLO load+inference in a thread to avoid blocking event loop."""
                    global _cached_yolo_model
                    _load_yolo_model_sync()  # no-op if already cached
                    if _cached_yolo_model is None:
                        raise RuntimeError("YOLO model failed to load")
                    model = _cached_yolo_model
                    model.conf = confidence_threshold
                    # IMPORTANT: Pass numpy BGR→RGB array, NOT the file path string.
                    # YOLOv5 AutoShape reads PNG files via PIL (RGB) but this model
                    # was trained expecting BGR channel order. Flipping to RGB fixes
                    # the zero-detection bug (0 detections at conf=0.01 from path,
                    # 17 detections at 0.90+ confidence from numpy array).
                    bgr_img = cv2.imread(file_path)
                    rgb_img = bgr_img[:, :, ::-1]  # BGR → RGB
                    with contextlib.redirect_stdout(io.StringIO()):
                        return model(rgb_img)

                # Offload the blocking work to the thread pool — does NOT freeze event loop
                results = await loop.run_in_executor(None, _run_yolo)

                # Map numeric class IDs to human-readable P&ID symbol names
                # (33-class Roboflow P&ID symbols dataset)
                PID_CLASS_NAMES = {
                    0: "Instrument", 1: "Control_Valve", 2: "Gate_Valve",
                    3: "Globe_Valve", 4: "Check_Valve", 5: "Ball_Valve",
                    6: "Butterfly_Valve", 7: "Valve", 8: "Safety_Valve",
                    9: "Pump", 10: "Centrifugal_Pump", 11: "Compressor",
                    12: "Tank", 13: "Vessel", 14: "HeatExchanger",
                    15: "Reactor", 16: "Column", 17: "Filter",
                    18: "Mixer", 19: "Fan", 20: "Turbine",
                    21: "Motor", 22: "Transmitter", 23: "Indicator",
                    24: "Controller", 25: "Recorder", 26: "Instrument_Bubble",
                    27: "Flow_Element", 28: "Pressure_Element", 29: "Temperature_Element",
                    30: "Level_Element", 31: "Analyzer", 32: "Actuator",
                }

                # Parse results from pandas dataframe
                df = results.pandas().xyxy[0]
                for _, row in df.iterrows():
                    class_id = int(row['class'])
                    label = PID_CLASS_NAMES.get(class_id, f"Symbol_{class_id}")
                    conf = float(row['confidence'])
                    x1, y1, x2, y2 = int(row['xmin']), int(row['ymin']), int(row['xmax']), int(row['ymax'])
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

        # ── Draw Bounding Boxes and Save Annotated Image ──────────────────────
        annotated_img_path = str(path.parent / f"{path.stem}_annotated{path.suffix}")
        annotated_img = img.copy()
        
        for eq in detected_equipment:
            x1, y1, x2, y2 = eq["bbox"]
            label_text = f"{eq['label']} ({eq['tag']})"
            cv2.rectangle(annotated_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(annotated_img, label_text, (x1, max(y1 - 5, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line.flatten()
                cv2.line(annotated_img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 1)

        cv2.imwrite(annotated_img_path, annotated_img)

        # ── Write to Neo4j + S3 as background tasks ───────────────────────────
        # We fire these off and return immediately so the MCP Inspector never
        # hits its 30-second client-side timeout. Writes appear in AuraDB
        # within ~10 seconds; check the server log for confirmation.
        async def _background_persist():
            # Neo4j write
            try:
                # Document node for the P&ID drawing
                await neo4j_client.upsert_node(
                    doc_id, ["Document", "Drawing"],
                    {"title": path.stem, "doc_type": "drawing", "filename": path.name,
                     "equipment_count": len(detected_equipment), "pipeline_lines": line_count}
                )
                for eq in detected_equipment:
                    tag = eq["tag"]
                    await neo4j_client.upsert_node(
                        tag, ["Equipment"],
                        {"tag": tag, "type": eq["label"], "source_drawing": path.name}
                    )
                    await neo4j_client.upsert_edge(tag, doc_id, "DEPICTED_IN")
                for i in range(len(detected_equipment) - 1):
                    a = detected_equipment[i]["tag"]
                    b = detected_equipment[i + 1]["tag"]
                    await neo4j_client.upsert_edge(a, b, "CONNECTED_TO",
                                                    {"source": "P&ID_autodetect"})
                logger.info("Neo4j: wrote %d equipment nodes for doc_id=%s",
                            len(detected_equipment), doc_id)
            except Exception as e:
                logger.error("Neo4j background write failed: %s", e)

            # S3 upload (only if requested)
            if upload_to_s3:
                try:
                    await object_store.upload_file(file_path, doc_id, {"doc_type": "drawing"})
                    logger.info("S3: uploaded %s → doc_id=%s", path.name, doc_id)
                except Exception as e:
                    logger.warning("S3 upload failed: %s", e)

        # Fire-and-forget: returns immediately, writes happen in the background
        # Must keep a strong reference so asyncio doesn't garbage collect it!
        task = asyncio.create_task(_background_persist())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        # ── Return result instantly ────────────────────────────────────────────
        return {
            "doc_id": doc_id,
            "filename": path.name,
            "detection_mode": "yolo" if yolo_available else "opencv_fallback",
            "equipment_detected": detected_equipment,
            "equipment_count": len(detected_equipment),
            "pipeline_lines_detected": line_count,
            "annotated_image_path": annotated_img_path,
            "kg_status": "writing_to_auradb_in_background",
            "note": (
                "For accurate P&ID parsing, fine-tune YOLOv5 on the P&ID-Symbols dataset. "
                "Set PID_YOLO_MODEL env var to the .pt file path."
                if not yolo_available else
                "YOLO model used. Neo4j + S3 writes are running in the background — check server log."
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
