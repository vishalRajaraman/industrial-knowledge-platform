"""
Knowledge engineering tools:
- extract_entities: Industrial NER with spaCy + custom patterns
- extract_temporal: Date/time normalization
- map_asset_hierarchy: Plant → Unit → Equipment taxonomy
"""
import asyncio
import logging
import os
import re
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("ikp.knowledge.ner")

# ── GLiNER setup ──────────────────────────────────────────────────────────────
_gliner_model = None

EQUIPMENT_TAG_PATTERNS = [
    r"\b[A-Z]{1,3}-\d{3,4}[A-Z]?\b",          # P-101A, HE-201
    r"\b[A-Z]{1,3}\d{4}[A-Z]?\b",              # P2003A
    r"\b(?:TAG|EQ|INST|FI|PI|TI|LI|AI|VI)-?\d+\b",  # FI-102
]

PARAMETER_PATTERNS = {
    "pressure": r"\d+\.?\d*\s*(?:bar|psi|kPa|MPa|kg/cm2)",
    "temperature": r"-?\d+\.?\d*\s*°?[CF]\b",
    "flow": r"\d+\.?\d*\s*(?:m3/hr|GPM|lpm|MMSCFD)",
    "vibration": r"\d+\.?\d*\s*(?:mm/s|in/s|mils)",
}

REGULATORY_PATTERNS = {
    "OISD": r"OISD[-\s]?(?:STD[-\s]?)?\d{3}(?:[-\s]?\d+)?",
    "Factory_Act": r"Factory\s+Act(?:\s+\d{4})?",
    "PESO": r"PESO(?:\s+Rules?)?",
    "IS_Standard": r"IS[-:\s]?\d{4}(?:[-:\s]Part[-:\s]?\d+)?",
    "API": r"API[-\s]?(?:RP|STD|TR|BUL|PUBL)[-\s]?\d+",
}

FAILURE_MODES = [
    "bearing failure", "seal failure", "seal leak", "shaft misalignment",
    "cavitation", "corrosion", "erosion", "fouling", "overpressure",
    "thermal runaway", "motor burnout", "insulation failure", "winding fault",
    "sensor drift", "transmitter failure", "control valve stuck", "tube leak",
    "vibration", "overheating", "underperformance", "plugging",
]


def _get_gliner():
    global _gliner_model
    if _gliner_model is None:
        try:
            from gliner import GLiNER
            # Assume models/gliner-ikp-v1 is at project root
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
            model_path = os.path.join(project_root, 'models', 'gliner-ikp-v1')
            
            if os.path.exists(model_path):
                logger.info(f"Loading fine-tuned GLiNER from {model_path}")
                _gliner_model = GLiNER.from_pretrained(model_path)
            else:
                logger.warning(f"Fine-tuned GLiNER not found at {model_path}. Loading base model.")
                _gliner_model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
        except ImportError:
            logger.error("GLiNER not installed. pip install gliner")
            _gliner_model = None
    return _gliner_model


async def _extract_entities_impl(text: str, doc_id: str = "") -> dict:
    """Core entity extraction — used internally by all ingest tools."""
    loop = asyncio.get_event_loop()

    def _run():
        result: dict[str, list] = {
            "equipment_tags": [],
            "process_parameters": [],
            "regulatory_references": [],
            "failure_modes": [],
            "persons": [],
            "dates": [],
            "chemicals": [],
        }

        # ── Regex-based extraction (fallback / complement) ─────────────────────────────
        for pat in EQUIPMENT_TAG_PATTERNS:
            for m in re.finditer(pat, text):
                tag = m.group().upper()
                if tag not in [e["text"] for e in result["equipment_tags"]]:
                    result["equipment_tags"].append({"text": tag, "start": m.start(), "end": m.end()})

        for param, pat in PARAMETER_PATTERNS.items():
            for m in re.finditer(pat, text, re.IGNORECASE):
                result["process_parameters"].append({"text": m.group(), "type": param, "start": m.start()})

        for framework, pat in REGULATORY_PATTERNS.items():
            for m in re.finditer(pat, text, re.IGNORECASE):
                result["regulatory_references"].append({"text": m.group(), "framework": framework})

        text_lower = text.lower()
        for mode in FAILURE_MODES:
            if mode in text_lower:
                idx = text_lower.find(mode)
                result["failure_modes"].append({"text": mode, "start": idx})

        # ── GLiNER NER (All domain entities) ────────────────────────────
        model = _get_gliner()
        if model:
            labels = ["Equipment Tag", "Process Parameter", "Regulatory Reference", "Failure Mode", "Person", "Date", "Chemical"]
            
            # GLiNER works best on shorter chunks, so we chunk the text into 2000-char windows with slight overlap.
            window_size = 2000
            overlap = 100
            windows = []
            
            # Create overlapping windows
            start_idx = 0
            while start_idx < len(text):
                end_idx = min(start_idx + window_size, len(text))
                windows.append((start_idx, text[start_idx:end_idx]))
                start_idx += window_size - overlap
                if end_idx == len(text):
                    break

            try:
                for w_start, window_text in windows:
                    entities = model.predict_entities(window_text, labels, threshold=0.3)
                    for ent in entities:
                        label = ent["label"]
                        text_val = ent["text"]
                        start = w_start + ent["start"]
                        
                        if label == "Equipment Tag":
                            # Avoid duplicates from regex
                            if text_val.upper() not in [e["text"].upper() for e in result["equipment_tags"]]:
                                result["equipment_tags"].append({"text": text_val, "start": start, "source": "gliner"})
                        elif label == "Process Parameter":
                            if text_val not in [e["text"] for e in result["process_parameters"]]:
                                result["process_parameters"].append({"text": text_val, "start": start, "source": "gliner"})
                        elif label == "Regulatory Reference":
                            if text_val not in [e["text"] for e in result["regulatory_references"]]:
                                result["regulatory_references"].append({"text": text_val, "start": start, "source": "gliner"})
                        elif label == "Failure Mode":
                            if text_val.lower() not in [e.get("text", "").lower() for e in result["failure_modes"]]:
                                result["failure_modes"].append({"text": text_val, "start": start, "source": "gliner"})
                        elif label == "Person":
                            if text_val not in [e["text"] for e in result["persons"]]:
                                result["persons"].append({"text": text_val, "start": start, "source": "gliner"})
                        elif label == "Date":
                            if text_val not in [e["text"] for e in result["dates"]]:
                                result["dates"].append({"text": text_val, "start": start, "source": "gliner"})
                        elif label == "Chemical":
                            if text_val not in [e["text"] for e in result["chemicals"]]:
                                result["chemicals"].append({"text": text_val, "start": start, "source": "gliner"})
            except Exception as e:
                logger.error(f"GLiNER prediction failed: {e}")

        logger.info(f"GLiNER Extracted for doc '{doc_id}': Equipment={len(result['equipment_tags'])}, Parameters={len(result['process_parameters'])}, Regulations={len(result['regulatory_references'])}, Failures={len(result['failure_modes'])}, Chemicals={len(result['chemicals'])}")
        if result['equipment_tags']: logger.info(f"Sample Equipment: {[e['text'] for e in result['equipment_tags'][:5]]}")
        if result['process_parameters']: logger.info(f"Sample Parameters: {[e['text'] for e in result['process_parameters'][:3]]}")
        if result['failure_modes']: logger.info(f"Sample Failures: {[e['text'] for e in result['failure_modes'][:3]]}")

        return result

    return await loop.run_in_executor(None, _run)


def register(mcp: FastMCP):

    @mcp.tool()
    async def extract_entities(text: str, doc_id: str = "") -> dict:
        """
        Extract industrial named entities from text using domain-specific NER.

        Extracts:
        - Equipment tags (P-101A, HE-201, V-301, FIC-102)
        - Process parameters (pressure: 15 bar, temperature: 350°C, flow: 100 m3/hr)
        - Regulatory references (OISD-154, API RP 686, IS:2825)
        - Failure modes (bearing failure, seal leak, cavitation, corrosion)
        - Personnel names and roles (via spaCy)
        - Dates and timestamps
        - Chemical names

        Uses a dual-pipeline: regex rules for industrial patterns + spaCy NER
        for general entities. For higher accuracy on industrial text, fine-tune
        a custom spaCy NER model (see post-execution checklist).

        Args:
            text: Raw text to extract entities from.
            doc_id: Optional source document identifier for provenance.

        Returns:
            Dict of entity_type → list of {text, start, confidence}.
        """
        return await _extract_entities_impl(text, doc_id)

    @mcp.tool()
    async def map_asset_hierarchy(entities: list[dict], context_text: str = "") -> dict:
        """
        Map detected equipment entities into the industrial asset hierarchy:
        Plant → Unit → Area → Equipment → Instrument.

        Uses equipment tag patterns and context text to infer hierarchy level.
        Returns a structured JSON hierarchy for Knowledge Graph population.

        Args:
            entities: List of equipment tag entities from extract_entities.
            context_text: Original document text for additional context.

        Returns:
            Nested asset hierarchy JSON with equipment → unit mappings.
        """
        # Tag prefix → equipment type mapping
        TYPE_MAP = {
            "P": "Pump", "C": "Compressor", "HE": "HeatExchanger",
            "V": "Vessel", "R": "Reactor", "T": "Column",
            "TK": "Tank", "FI": "FlowIndicator", "PI": "PressureIndicator",
            "TI": "TemperatureIndicator", "LI": "LevelIndicator",
            "FIC": "FlowController", "PIC": "PressureController",
            "TIC": "TemperatureController", "LIC": "LevelController",
            "VLV": "Valve", "PSV": "PressureSafetyValve",
        }

        hierarchy = {"Plant": {"Units": {}}}
        processed = []

        for ent in entities:
            tag = ent.get("text", "").upper()
            # Extract prefix (e.g., "P" from "P-101A")
            m = re.match(r"^([A-Z]+)", tag.replace("-", ""))
            prefix = m.group(1) if m else "UNK"
            eq_type = TYPE_MAP.get(prefix, "Equipment")

            # Infer unit from tag number (hundreds digit)
            m2 = re.search(r"(\d+)", tag)
            unit_num = int(m2.group(1)) // 100 * 100 if m2 else 0
            unit_name = f"Unit-{unit_num:03d}" if unit_num else "General"

            if unit_name not in hierarchy["Plant"]["Units"]:
                hierarchy["Plant"]["Units"][unit_name] = {"Equipment": []}
            hierarchy["Plant"]["Units"][unit_name]["Equipment"].append({
                "tag": tag, "type": eq_type,
            })
            processed.append({"tag": tag, "type": eq_type, "unit": unit_name})

        return {
            "hierarchy": hierarchy,
            "equipment_mapped": processed,
            "total_equipment": len(processed),
        }
