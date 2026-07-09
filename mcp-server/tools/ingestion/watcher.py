"""
Ingestion — File watcher (local directory) + AWS S3 bucket watcher.
Triggers appropriate ingest_* tools when new files appear.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("ikp.ingest.watcher")

# Extension → doc_type mapping
EXT_DOC_TYPE = {
    ".pdf": "pdf",
    ".xlsx": "excel",
    ".xls": "excel",
    ".csv": "excel",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".tif": "image",
    ".eml": "email",
    ".msg": "email",
}

_watched_dirs: dict[str, asyncio.Task] = {}
_s3_watcher_task: asyncio.Task | None = None


async def _process_file(file_path: str, doc_type_override: str | None = None):
    """Route a new file to the correct ingestion tool."""
    ext = Path(file_path).suffix.lower()
    doc_type = doc_type_override or EXT_DOC_TYPE.get(ext, "general")

    # Import lazily to avoid circular imports at module load
    if ext == ".pdf":
        from tools.ingestion.pdf_tool import ingest_pdf  # type: ignore
        result = await ingest_pdf(file_path, doc_type=doc_type)
    elif ext in (".xlsx", ".xls", ".csv"):
        from tools.ingestion.excel_tool import ingest_excel  # type: ignore
        result = await ingest_excel(file_path)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
        # Try P&ID first if file name suggests it
        name_lower = Path(file_path).stem.lower()
        if any(k in name_lower for k in ("pid", "p&id", "piping", "drawing", "dwg")):
            from tools.ingestion.pid_tool import parse_pid  # type: ignore
            result = await parse_pid(file_path)
        else:
            from tools.ingestion.ocr_tool import ocr_document  # type: ignore
            result = await ocr_document(file_path)
    elif ext in (".eml", ".msg"):
        from tools.ingestion.pdf_tool import ingest_pdf  # email → text PDF fallback
        result = {"skipped": True, "reason": "Email ingestion not yet wired"}
    else:
        result = {"skipped": True, "file": file_path, "reason": f"Unsupported extension: {ext}"}

    logger.info("Ingested %s → %s", file_path, result)
    return result


def register(mcp: FastMCP):

    @mcp.tool()
    async def watch_local_folder(
        folder_path: str,
        poll_interval_seconds: int = 30,
        recursive: bool = False,
    ) -> dict:
        """
        Start monitoring a LOCAL directory for new files.
        When a new file appears, automatically triggers the correct ingestion tool
        (ingest_pdf, ingest_excel, ocr_document, or parse_pid) based on extension.

        This is a background task — it runs continuously until stopped.
        Also triggers on files already present that haven't been ingested.

        Args:
            folder_path: Absolute path to the directory to monitor.
            poll_interval_seconds: How often to check for new files (default: 30s).
            recursive: Whether to watch subdirectories too.

        Returns:
            Status dict with watcher ID and initial file count.
        """
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return {"error": f"Directory does not exist: {folder_path}"}

        if folder_path in _watched_dirs:
            return {"status": "already_watching", "folder": folder_path}

        processed: set[str] = set()

        async def _watch_loop():
            logger.info("Watching folder: %s (every %ds)", folder_path, poll_interval_seconds)
            while True:
                try:
                    pattern = "**/*" if recursive else "*"
                    for f in folder.glob(pattern):
                        if f.is_file() and str(f) not in processed:
                            ext = f.suffix.lower()
                            if ext in EXT_DOC_TYPE:
                                processed.add(str(f))
                                asyncio.create_task(_process_file(str(f)))
                except Exception as e:
                    logger.error("Watcher error: %s", e)
                await asyncio.sleep(poll_interval_seconds)

        task = asyncio.create_task(_watch_loop())
        _watched_dirs[folder_path] = task

        # Count existing files
        initial_files = [f for f in folder.glob("*") if f.is_file() and f.suffix.lower() in EXT_DOC_TYPE]
        return {
            "status": "watching",
            "folder": folder_path,
            "poll_interval_seconds": poll_interval_seconds,
            "initial_file_count": len(initial_files),
            "supported_extensions": list(EXT_DOC_TYPE.keys()),
        }

    @mcp.tool()
    async def stop_watching_folder(folder_path: str) -> dict:
        """
        Stop monitoring a local folder that was started with watch_local_folder.

        Args:
            folder_path: The folder path to stop watching.
        """
        if folder_path not in _watched_dirs:
            return {"status": "not_watching", "folder": folder_path}
        _watched_dirs[folder_path].cancel()
        del _watched_dirs[folder_path]
        return {"status": "stopped", "folder": folder_path}

    @mcp.tool()
    async def list_active_watchers() -> dict:
        """
        List all currently active local folder watchers.
        Returns folder paths and their status.
        """
        return {
            "local_watchers": [
                {"folder": k, "active": not v.done()} for k, v in _watched_dirs.items()
            ],
            "s3_watcher_active": _s3_watcher_task is not None and not _s3_watcher_task.done(),
        }
