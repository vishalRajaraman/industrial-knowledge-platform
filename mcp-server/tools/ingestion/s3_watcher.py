"""
AWS S3 Bucket Watcher — polls an S3 bucket/prefix for new objects and
triggers the ingestion pipeline.

Two modes:
  1. SQS mode (recommended for production):
       S3 sends ObjectCreated events to an SQS queue. This loop long-polls
       the queue (WaitTimeSeconds=20) so new uploads trigger ingestion in
       near real-time without hammering the S3 ListObjects API.
       Requires: SQS_QUEUE_URL env var + S3 → SQS notification in AWS Console.

  2. Polling mode (simple / no SQS setup needed):
       Lists the bucket every S3_POLL_INTERVAL seconds and picks up objects
       whose LastModified timestamp is newer than the last run.
       State is persisted to .s3_watcher_state.json so server restarts do
       NOT re-ingest already-processed files.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("ikp.ingest.s3_watcher")

# ── Config ────────────────────────────────────────────────────────────────────
AWS_REGION    = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
S3_BUCKET     = os.getenv("S3_BUCKET", "industreak-raw-assets")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")          # optional
POLL_INTERVAL = int(os.getenv("S3_POLL_INTERVAL", "60"))

# State file — persists the last-checked timestamp across restarts
_STATE_FILE = Path(__file__).resolve().parent / ".s3_watcher_state.json"

EXT_MAP: dict[str, str] = {
    ".pdf":  "pdf",
    ".xlsx": "excel",
    ".xls":  "excel",
    ".csv":  "excel",
    ".png":  "image",
    ".jpg":  "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".tif":  "image",
}

_s3_watcher_task: asyncio.Task | None = None


# ── State persistence ─────────────────────────────────────────────────────────

def _load_state() -> dict:
    """Load persisted watcher state (last_checked timestamp, processed keys)."""
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not read watcher state file: %s", exc)
    return {"last_checked": None, "processed_keys": []}


def _save_state(state: dict) -> None:
    """Persist watcher state to disk."""
    try:
        _STATE_FILE.write_text(
            json.dumps(state, indent=2, default=str), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning("Could not save watcher state: %s", exc)


# ── S3 client factory ─────────────────────────────────────────────────────────

def _get_s3_client():
    """Build an AWS S3 client from environment credentials."""
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


# ── Ingestion helper ──────────────────────────────────────────────────────────

async def _download_and_ingest(s3_key: str, bucket: str) -> None:
    """
    Download a single S3 object to a temp file, route it to the correct
    ingestion tool, then delete the temp file.

    Uses try/finally so the temp file is always cleaned up even on error.
    """
    ext = Path(s3_key).suffix.lower()
    if ext not in EXT_MAP:
        logger.debug("Skipping unsupported S3 object: %s", s3_key)
        return

    tmp_path: str | None = None
    try:
        # Download to a named temp file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name

        s3 = _get_s3_client()
        s3.download_file(bucket, s3_key, tmp_path)
        logger.info("Downloaded s3://%s/%s → %s", bucket, s3_key, tmp_path)

        # Route by extension / key name
        key_lower = s3_key.lower()
        if ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif") and any(
            k in key_lower for k in ("pid", "p_id", "piping", "drawing", "dwg")
        ):
            from tools.ingestion.pid_tool import parse_pid  # type: ignore
            result = await parse_pid(tmp_path)

        elif ext == ".pdf":
            from tools.ingestion.pdf_tool import ingest_pdf  # type: ignore
            # upload_to_s3=False because the file is already in S3
            result = await ingest_pdf(tmp_path, upload_to_s3=False)

        elif ext in (".xlsx", ".xls", ".csv"):
            from tools.ingestion.excel_tool import ingest_excel  # type: ignore
            result = await ingest_excel(tmp_path)

        else:
            from tools.ingestion.ocr_tool import ocr_document  # type: ignore
            result = await ocr_document(tmp_path)

        logger.info("S3 ingestion complete: %s → doc_id=%s", s3_key, result.get("doc_id", "?"))

    except Exception as exc:
        logger.error("S3 ingestion failed for %s: %s", s3_key, exc, exc_info=True)

    finally:
        # Always clean up the temp file
        if tmp_path and Path(tmp_path).exists():
            try:
                os.unlink(tmp_path)
            except OSError as exc:
                logger.warning("Could not delete temp file %s: %s", tmp_path, exc)


# ── SQS event loop ────────────────────────────────────────────────────────────

async def _sqs_poll_loop(queue_url: str, bucket: str) -> None:
    """
    Long-poll an SQS queue for S3 ObjectCreated event notifications.

    Each SQS message body is a JSON envelope from S3 (via SNS or direct S3
    notification). We parse out the object key and fire ingestion.

    Recommended for production — near real-time (< 5 s latency) with no
    repeated ListObjects calls.
    """
    sqs = boto3.client("sqs", region_name=AWS_REGION)
    processed_keys: set[str] = set(
        _load_state().get("processed_keys", [])
    )
    logger.info("SQS watcher started: %s", queue_url)

    while True:
        try:
            resp = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,   # long-polling — reduces empty calls
            )
            for msg in resp.get("Messages", []):
                try:
                    body = json.loads(msg["Body"])
                    # S3 → SNS → SQS wraps in another JSON layer
                    if "Message" in body:
                        body = json.loads(body["Message"])
                    for record in body.get("Records", []):
                        if record.get("eventSource") == "aws:s3":
                            s3_key = record["s3"]["object"]["key"]
                            if s3_key not in processed_keys:
                                processed_keys.add(s3_key)
                                asyncio.create_task(_download_and_ingest(s3_key, bucket))
                except Exception as parse_exc:
                    logger.warning("SQS message parse error: %s", parse_exc)

                # Always delete the message so it doesn't reappear
                sqs.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=msg["ReceiptHandle"],
                )

            # Persist processed keys periodically
            _save_state({"processed_keys": list(processed_keys)})

        except asyncio.CancelledError:
            logger.info("SQS watcher cancelled.")
            raise
        except Exception as exc:
            logger.error("SQS poll error: %s", exc, exc_info=True)
            await asyncio.sleep(5)  # back off on error

        await asyncio.sleep(1)


# ── S3 polling loop ───────────────────────────────────────────────────────────

async def _s3_poll_loop(bucket: str, prefix: str, interval: int) -> None:
    """
    Polling fallback — lists the bucket every `interval` seconds and
    ingests objects whose LastModified is newer than the last check.

    State (last_checked timestamp) is saved to disk so restarts do NOT
    re-ingest already-processed files.
    """
    state = _load_state()
    last_checked_str: str | None = state.get("last_checked")
    processed_keys: set[str] = set(state.get("processed_keys", []))

    if last_checked_str:
        last_checked = datetime.fromisoformat(last_checked_str)
        logger.info(
            "S3 polling resumed — last checked: %s", last_checked.isoformat()
        )
    else:
        # First run: only pick up objects from this point forward
        last_checked = datetime.now(tz=timezone.utc)
        logger.info(
            "S3 polling started fresh — watermark set to: %s",
            last_checked.isoformat(),
        )

    logger.info(
        "S3 poller active: s3://%s/%s every %ds", bucket, prefix or "(all)", interval
    )

    while True:
        try:
            run_start = datetime.now(tz=timezone.utc)

            s3 = _get_s3_client()
            kwargs: dict[str, Any] = {"Bucket": bucket}
            if prefix:
                kwargs["Prefix"] = prefix

            # Paginate through all matching objects
            new_objects: list[str] = []
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(**kwargs):
                for obj in page.get("Contents", []):
                    key: str = obj["Key"]
                    last_mod: datetime = obj["LastModified"]
                    # Ensure timezone-aware for comparison
                    if last_mod.tzinfo is None:
                        last_mod = last_mod.replace(tzinfo=timezone.utc)

                    if last_mod > last_checked and key not in processed_keys:
                        new_objects.append(key)

            for key in new_objects:
                processed_keys.add(key)
                logger.info("New S3 object detected: %s", key)
                asyncio.create_task(_download_and_ingest(key, bucket))

            # Advance the watermark and persist
            last_checked = run_start
            _save_state({
                "last_checked": last_checked.isoformat(),
                "processed_keys": list(processed_keys),
            })

            if new_objects:
                logger.info("S3 poll: found %d new object(s)", len(new_objects))

        except asyncio.CancelledError:
            logger.info("S3 poller cancelled.")
            raise
        except Exception as exc:
            logger.error("S3 poll error: %s", exc, exc_info=True)

        await asyncio.sleep(interval)


# ── MCP tool registration ─────────────────────────────────────────────────────

def register(mcp: FastMCP) -> None:

    @mcp.tool()
    async def watch_s3_bucket(
        bucket: str = "",
        prefix: str = "",
        poll_interval_seconds: int = 0,
        use_sqs: bool = False,
    ) -> dict:
        """
        Start watching an AWS S3 bucket for new files.

        When a new file is uploaded to the bucket/prefix, it is automatically
        downloaded and routed to the correct ingestion pipeline
        (ingest_pdf, ingest_excel, ocr_document, or parse_pid).

        Two modes:
          • SQS mode (recommended, near real-time):
              Reads S3 ObjectCreated notifications from an SQS queue.
              Requires SQS_QUEUE_URL env var and S3 → SQS notification
              configured in AWS Console. See setup steps in walkthrough.

          • Polling mode (simple, no AWS setup needed beyond S3 credentials):
              Lists the bucket every poll_interval_seconds and picks up
              objects with a LastModified timestamp newer than the last run.
              State is persisted so restarts don't re-ingest old files.

        Args:
            bucket:                S3 bucket name (defaults to S3_BUCKET env var).
            prefix:                Key prefix filter, e.g. "uploads/" ('' = all).
            poll_interval_seconds: Polling interval in seconds. Defaults to
                                   S3_POLL_INTERVAL env var (60s).
            use_sqs:               If True and SQS_QUEUE_URL is set, use SQS
                                   event mode instead of polling.

        Returns:
            Status dict with watcher mode, bucket, and configuration details.
        """
        global _s3_watcher_task

        target_bucket = bucket or S3_BUCKET
        if not target_bucket:
            return {
                "error": (
                    "S3 bucket not configured. "
                    "Set S3_BUCKET in .env or pass the bucket argument."
                )
            }

        if _s3_watcher_task and not _s3_watcher_task.done():
            return {"status": "already_watching", "bucket": target_bucket}

        interval = poll_interval_seconds or POLL_INTERVAL

        if use_sqs and SQS_QUEUE_URL:
            _s3_watcher_task = asyncio.create_task(
                _sqs_poll_loop(SQS_QUEUE_URL, target_bucket),
                name="s3-watcher:sqs",
            )
            mode = "sqs"
            mode_detail = f"SQS queue: {SQS_QUEUE_URL}"
        else:
            _s3_watcher_task = asyncio.create_task(
                _s3_poll_loop(target_bucket, prefix, interval),
                name="s3-watcher:polling",
            )
            mode = "polling"
            mode_detail = f"every {interval}s"

        return {
            "status": "watching",
            "bucket": target_bucket,
            "prefix": prefix or "(all objects)",
            "mode": mode,
            "mode_detail": mode_detail,
            "state_file": str(_STATE_FILE),
            "message": (
                f"S3 watcher active ({mode} mode). "
                f"Upload files to s3://{target_bucket}/{prefix} to trigger ingestion."
            ),
        }

    # ─────────────────────────────────────────────────────────────────────────

    @mcp.tool()
    async def stop_s3_watcher() -> dict:
        """
        Stop the active S3 bucket watcher.
        The last-checked timestamp is preserved so the next start resumes
        from where it left off.
        """
        global _s3_watcher_task

        if not _s3_watcher_task or _s3_watcher_task.done():
            return {"status": "not_watching"}

        _s3_watcher_task.cancel()
        try:
            await _s3_watcher_task
        except asyncio.CancelledError:
            pass

        _s3_watcher_task = None
        logger.info("S3 watcher stopped.")
        return {"status": "stopped", "state_preserved": str(_STATE_FILE)}

    # ─────────────────────────────────────────────────────────────────────────

    @mcp.tool()
    async def reset_s3_watcher_state() -> dict:
        """
        Clear the persisted S3 watcher state (last_checked timestamp and
        processed key list). The next watch_s3_bucket call will re-scan
        the bucket from scratch.

        Use this if you want to re-ingest all existing S3 objects.
        """
        if _STATE_FILE.exists():
            _STATE_FILE.unlink()
        return {"status": "reset", "message": "S3 watcher state cleared — next start will re-scan all objects."}
