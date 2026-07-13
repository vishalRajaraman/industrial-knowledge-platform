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
import logging
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("ikp.ingest.watcher")

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

# ── Active watcher registry ───────────────────────────────────────────────────
# key: folder_path → {"observer": Observer, "task": asyncio.Task, "queue": asyncio.Queue}
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


# ── Watchdog event handler ────────────────────────────────────────────────────

class _IKPEventHandler(FileSystemEventHandler):
    """
    Watchdog event handler that puts newly created/moved-in file paths
    into an asyncio.Queue that is consumed by the async watcher task.

    Watchdog runs its callbacks in a background thread; the queue is the
    thread-safe bridge into the event loop.
    """

    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._queue = queue
        self._loop = loop

    def _enqueue(self, path: str) -> None:
        """Thread-safe: schedule an item onto the asyncio queue."""
        self._loop.call_soon_threadsafe(self._queue.put_nowait, path)

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore[override]
        """Catch files moved/renamed *into* the watched folder (e.g. cut-paste)."""
        if not event.is_directory:
            self._enqueue(event.dest_path)


# ── Async consumer task ───────────────────────────────────────────────────────

async def _consumer_task(
    queue: asyncio.Queue,
    processed: set[str],
    folder_path: str,
) -> None:
    """
    Drains the file-event queue and calls _process_file() for each new path.
    Runs indefinitely until the asyncio task is cancelled.
    """
    logger.info("Watcher consumer ready for: %s", folder_path)
    while True:
        try:
            file_path = await queue.get()
            abs_path = str(Path(file_path).resolve())

            if abs_path in processed:
                queue.task_done()
                continue

            ext = Path(abs_path).suffix.lower()
            if ext not in EXT_DOC_TYPE:
                queue.task_done()
                continue

            processed.add(abs_path)
            # Fire and forget — don't block the consumer
            asyncio.create_task(_process_file(abs_path))
            queue.task_done()

        except asyncio.CancelledError:
            logger.info("Watcher consumer stopped for: %s", folder_path)
            raise
        except Exception as exc:
            logger.error("Watcher consumer error: %s", exc, exc_info=True)


# ── MCP tool registration ─────────────────────────────────────────────────────

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def watch_local_folder(
        folder_path: str = "",
        recursive: bool | None = None,
        scan_existing: bool = True,
    ) -> dict:
        """
        Start monitoring a LOCAL directory for new files using OS-native
        filesystem events (watchdog). Files are detected instantly — no polling.

        When a new file appears the correct ingestion pipeline is triggered
        automatically:
          • .pdf           → ingest_pdf
          • .xlsx/.xls/.csv → ingest_excel
          • .png/.jpg/…    → parse_pid (if name contains "pid") or ocr_document
          • .eml/.msg      → (email — not yet wired)

        Args:
            folder_path:    Absolute path to the directory to monitor.
                            Defaults to WATCH_FOLDER env var, or
                            data/watch_inbox inside the project root.
            recursive:      Watch subdirectories too. Defaults to
                            WATCH_RECURSIVE env var (false).
            scan_existing:  If True, immediately ingest any files already
                            present in the folder on startup.

        Returns:
            Status dict with watcher details and initial file count.
        """
        target = Path(folder_path or _DEFAULT_WATCH_FOLDER).resolve()

        # Auto-create the folder if it doesn't exist
        target.mkdir(parents=True, exist_ok=True)
        folder_str = str(target)

        if folder_str in _active_watchers:
            return {"status": "already_watching", "folder": folder_str}

        use_recursive = recursive if recursive is not None else _DEFAULT_RECURSIVE

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()
        processed: set[str] = set()

        # ── Scan pre-existing files ──────────────────────────────────────────
        initial_files: list[str] = []
        if scan_existing:
            pattern = "**/*" if use_recursive else "*"
            for f in target.glob(pattern):
                if f.is_file() and f.suffix.lower() in EXT_DOC_TYPE:
                    abs_f = str(f.resolve())
                    initial_files.append(abs_f)
                    processed.add(abs_f)          # mark as seen
                    asyncio.create_task(_process_file(abs_f))

        # ── Start watchdog observer (runs in its own OS thread) ───────────────
        handler = _IKPEventHandler(queue, loop)
        observer = Observer()
        observer.schedule(handler, folder_str, recursive=use_recursive)
        observer.start()
        logger.info(
            "Watchdog observer started: %s (recursive=%s)", folder_str, use_recursive
        )

        # ── Start async consumer task ─────────────────────────────────────────
        task = asyncio.create_task(
            _consumer_task(queue, processed, folder_str),
            name=f"watcher:{folder_str}",
        )

        _active_watchers[folder_str] = {
            "observer": observer,
            "task": task,
            "queue": queue,
            "recursive": use_recursive,
        }

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
