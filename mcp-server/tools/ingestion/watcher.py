"""
Ingestion — Local directory watcher.

Uses Python's `watchdog` library to hook into the OS filesystem event API:
  • Windows  → ReadDirectoryChangesW  (instant, no polling lag)
  • Linux    → inotify
  • macOS    → FSEvents

When a supported file appears in the watched folder the correct ingestion
tool (ingest_pdf, ingest_excel, ocr_document, parse_pid) is called
automatically via an asyncio background task.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

# Ensure we use a logger that definitely writes to the file
logger = logging.getLogger("industreak-mcp.watcher")
# Explicitly add the file handler if it's missing (to satisfy user request)
_file_handler = logging.FileHandler("mcp_server.log", mode="a", encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
logger.addHandler(_file_handler)
logger.setLevel(logging.INFO)

# ── Extension → doc_type mapping ─────────────────────────────────────────────
EXT_DOC_TYPE: dict[str, str] = {
    ".pdf":  "pdf",
    ".xlsx": "excel",
    ".xls":  "excel",
    ".csv":  "excel",
    ".png":  "image",
    ".jpg":  "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".tif":  "image",
    ".eml":  "email",
    ".msg":  "email",
}

# ── Environment defaults ──────────────────────────────────────────────────────
_DEFAULT_WATCH_FOLDER = os.getenv(
    "WATCH_FOLDER",
    str(Path(__file__).resolve().parents[4] / "data" / "watch_inbox"),
)
_DEFAULT_RECURSIVE = os.getenv("WATCH_RECURSIVE", "false").lower() == "true"
_STATE_FILE = Path(__file__).resolve().parents[4] / "data" / "watcher_state.json"

# ── State persistence ─────────────────────────────────────────────────────────

def _load_processed_state() -> set[str]:
    """Load previously processed file paths from JSON state."""
    if _STATE_FILE.exists():
        try:
            with open(_STATE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as exc:
            logger.error("Failed to load watcher state: %s", exc)
    return set()

def _save_processed_state(processed: set[str]) -> None:
    """Save processed file paths to JSON state."""
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed), f, indent=2)
    except Exception as exc:
        logger.error("Failed to save watcher state: %s", exc)


# ── Active watcher registry ───────────────────────────────────────────────────
# key: folder_path → {"task": asyncio.Task, "recursive": bool}
_active_watchers: dict[str, dict[str, Any]] = {}

# ── Async ingestion router ────────────────────────────────────────────────────

async def _process_file(file_path: str) -> dict:
    """Route a new file to the correct ingestion tool based on its extension."""
    ext = Path(file_path).suffix.lower()
    doc_type = EXT_DOC_TYPE.get(ext, "general")

    if ext not in EXT_DOC_TYPE:
        logger.debug("Skipping unsupported file: %s", file_path)
        return {"skipped": True, "file": file_path, "reason": f"Unsupported extension: {ext}"}

    logger.info("Processing new file: %s (type=%s)", file_path, doc_type)

    try:
        if ext == ".pdf":
            from tools.ingestion.pdf_tool import ingest_pdf  # type: ignore
            result = await ingest_pdf(file_path, doc_type=doc_type)

        elif ext in (".xlsx", ".xls", ".csv"):
            from tools.ingestion.excel_tool import ingest_excel  # type: ignore
            result = await ingest_excel(file_path)

        elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
            name_lower = Path(file_path).stem.lower()
            if any(k in name_lower for k in ("pid", "p&id", "piping", "drawing", "dwg")):
                from tools.ingestion.pid_tool import parse_pid  # type: ignore
                result = await parse_pid(file_path)
            else:
                from tools.ingestion.ocr_tool import ocr_document  # type: ignore
                result = await ocr_document(file_path)

        elif ext in (".eml", ".msg"):
            result = {"skipped": True, "reason": "Email ingestion not yet wired"}

        else:
            result = {"skipped": True, "file": file_path, "reason": f"Unsupported extension: {ext}"}

    except Exception as exc:
        logger.error("Ingestion failed for %s: %s", file_path, exc, exc_info=True)
        result = {"error": str(exc), "file": file_path}

    logger.info("Ingested %s → %s", file_path, result)
    return result

# Store background tasks globally to prevent GC or cancellation from TaskGroups
_background_tasks = set()

# ── Async Polling Consumer (Replaces Watchdog) ────────────────────────────────

async def _polling_task(
    folder_path: str,
    processed: set[str],
    recursive: bool,
) -> None:
    """
    Robust purely-async polling watcher. Avoids all thread/event loop issues
    caused by watchdog when embedded inside an MCP/FastAPI server.
    """
    logger.info("Polling watcher ready for: %s", folder_path)
    target = Path(folder_path)
    pattern = "**/*" if recursive else "*"
    
    while True:
        try:
            if not target.exists():
                await asyncio.sleep(2.0)
                continue
                
            new_files_found = False
            for f in target.glob(pattern):
                if not f.is_file():
                    continue
                    
                abs_path = str(f.resolve())
                if abs_path in processed:
                    continue
                    
                ext = f.suffix.lower()
                if ext not in EXT_DOC_TYPE:
                    continue
                    
                # New file found!
                logger.info("Detected new file: %s", abs_path)
                processed.add(abs_path)
                new_files_found = True
                
                # Spawn process task globally
                process_task = asyncio.create_task(_process_file(abs_path))
                _background_tasks.add(process_task)
                process_task.add_done_callback(_background_tasks.discard)
                
            if new_files_found:
                _save_processed_state(processed)
                
        except asyncio.CancelledError:
            logger.info("Polling watcher stopped for: %s", folder_path)
            raise
        except Exception as exc:
            logger.error("Polling watcher error: %s", exc, exc_info=True)
            
        # Poll every 1.5 seconds
        await asyncio.sleep(1.5)


# ── MCP tool registration ─────────────────────────────────────────────────────

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def watch_local_folder(
        folder_path: str = "",
        recursive: bool | None = None,
        scan_existing: bool = True,
    ) -> dict:
        """
        Start monitoring a LOCAL directory for new files using robust async polling.
        Files are detected automatically.

        Args:
            folder_path:    Absolute path to the directory to monitor.
                            Defaults to WATCH_FOLDER env var.
            recursive:      Watch subdirectories too. Defaults to false.
            scan_existing:  If True, immediately ingest any files already
                            present in the folder on startup.

        Returns:
            Status dict with watcher details and initial file count.
        """
        logger.info("watch_local_folder called with path: %s", folder_path)
        target = Path(folder_path or _DEFAULT_WATCH_FOLDER).resolve()

        # Auto-create the folder if it doesn't exist
        target.mkdir(parents=True, exist_ok=True)
        folder_str = str(target)

        if folder_str in _active_watchers:
            logger.info("Already watching %s", folder_str)
            return {"status": "already_watching", "folder": folder_str}

        use_recursive = recursive if recursive is not None else _DEFAULT_RECURSIVE
        processed: set[str] = _load_processed_state()

        # ── Scan pre-existing files ──────────────────────────────────────────
        initial_files: list[str] = []
        if scan_existing:
            pattern = "**/*" if use_recursive else "*"
            new_files_found = False
            for f in target.glob(pattern):
                if f.is_file() and f.suffix.lower() in EXT_DOC_TYPE:
                    abs_f = str(f.resolve())
                    if abs_f not in processed:
                        initial_files.append(abs_f)
                        processed.add(abs_f)          # mark as seen
                        new_files_found = True
                        ptask = asyncio.create_task(_process_file(abs_f))
                        _background_tasks.add(ptask)
                        ptask.add_done_callback(_background_tasks.discard)
            
            if new_files_found:
                _save_processed_state(processed)

        # ── Start async polling task ─────────────────────────────────────────
        task = asyncio.create_task(
            _polling_task(folder_str, processed, use_recursive),
            name=f"watcher:{folder_str}",
        )
        _background_tasks.add(task)

        _active_watchers[folder_str] = {
            "task": task,
            "recursive": use_recursive,
        }

        logger.info("Successfully activated polling watcher!")
        return {
            "status": "watching",
            "folder": folder_str,
            "recursive": use_recursive,
            "scan_existing": scan_existing,
            "initial_files_queued": len(initial_files),
            "supported_extensions": list(EXT_DOC_TYPE.keys()),
            "message": (
                f"Watchdog active — drop files into '{folder_str}' "
                "to trigger ingestion automatically."
            ),
        }

    # ─────────────────────────────────────────────────────────────────────────

    @mcp.tool()
    async def stop_watching_folder(folder_path: str = "") -> dict:
        """
        Stop monitoring a local folder that was started with watch_local_folder.

        Args:
            folder_path: The folder path to stop (defaults to WATCH_FOLDER env var).
        """
        target = str(Path(folder_path or _DEFAULT_WATCH_FOLDER).resolve())

        if target not in _active_watchers:
            return {"status": "not_watching", "folder": target}

        entry = _active_watchers.pop(target)

        # Stop watchdog observer thread
        entry["observer"].stop()
        entry["observer"].join(timeout=5)

        # Cancel asyncio consumer
        entry["task"].cancel()
        try:
            await entry["task"]
        except asyncio.CancelledError:
            pass

        logger.info("Watcher stopped: %s", target)
        return {"status": "stopped", "folder": target}

    # ─────────────────────────────────────────────────────────────────────────

    @mcp.tool()
    async def list_active_watchers() -> dict:
        """
        List all currently active local folder watchers and their status.
        """
        return {
            "local_watchers": [
                {
                    "folder": k,
                    "recursive": v["recursive"],
                    "active": not v["task"].done(),
                    "queue_depth": v["queue"].qsize(),
                }
                for k, v in _active_watchers.items()
            ],
            "total": len(_active_watchers),
        }
