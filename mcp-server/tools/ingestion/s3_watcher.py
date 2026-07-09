"""
AWS S3 Bucket Watcher — polls an S3 bucket/prefix for new objects and
triggers the ingestion pipeline. Designed to work with S3 Event Notifications
(SNS/SQS) or in polling mode.

This enables the pipeline to trigger automatically when a file is dropped
into the configured S3 bucket from ANY source (web upload, CLI, another system).
"""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import boto3
from mcp.server.fastmcp import FastMCP

from core import object_store

logger = logging.getLogger("ikp.ingest.s3_watcher")

AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
S3_BUCKET = os.getenv("S3_BUCKET", "industreak-raw-assets")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")   # optional: S3→SQS event notifications
POLL_INTERVAL = int(os.getenv("S3_POLL_INTERVAL", "60"))

_processed_keys: set[str] = set()
_s3_watcher_task: asyncio.Task | None = None

EXT_MAP = {
    ".pdf": "pdf", ".xlsx": "excel", ".xls": "excel", ".csv": "excel",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".tiff": "image",
}


async def _download_and_ingest(s3_key: str):
    """Download from S3 and route to correct ingestion tool."""
    ext = Path(s3_key).suffix.lower()
    if ext not in EXT_MAP:
        logger.debug("Skipping unsupported file type: %s", s3_key)
        return

    try:
        s3 = boto3.client("s3",
            region_name=AWS_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name

        s3.download_file(S3_BUCKET, s3_key, tmp_path)
        logger.info("Downloaded s3://%s/%s → %s", S3_BUCKET, s3_key, tmp_path)

        # Detect P&ID from key name
        key_lower = s3_key.lower()
        if ext in (".png", ".jpg", ".jpeg", ".tiff") and any(
            k in key_lower for k in ("pid", "p_id", "piping", "drawing")
        ):
            from tools.ingestion.pid_tool import parse_pid  # type: ignore
            result = await parse_pid(tmp_path)
        elif ext == ".pdf":
            from tools.ingestion.pdf_tool import ingest_pdf  # type: ignore
            result = await ingest_pdf(tmp_path, upload_to_s3=False)  # already in S3
        elif ext in (".xlsx", ".xls", ".csv"):
            from tools.ingestion.excel_tool import ingest_excel  # type: ignore
            result = await ingest_excel(tmp_path)
        else:
            from tools.ingestion.ocr_tool import ocr_document  # type: ignore
            result = await ocr_document(tmp_path)

        os.unlink(tmp_path)
        logger.info("S3 ingestion complete: %s → %s", s3_key, result.get("doc_id", "?"))
    except Exception as e:
        logger.error("S3 ingestion failed for %s: %s", s3_key, e, exc_info=True)


async def _sqs_poll_loop(queue_url: str):
    """Poll SQS queue for S3 event notifications (recommended for production)."""
    sqs = boto3.client("sqs", region_name=AWS_REGION)
    logger.info("Starting SQS polling: %s", queue_url)
    while True:
        try:
            resp = sqs.receive_message(
                QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=20
            )
            for msg in resp.get("Messages", []):
                body = json.loads(msg["Body"])
                for record in body.get("Records", []):
                    if record.get("eventSource") == "aws:s3":
                        s3_key = record["s3"]["object"]["key"]
                        if s3_key not in _processed_keys:
                            _processed_keys.add(s3_key)
                            asyncio.create_task(_download_and_ingest(s3_key))
                sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"])
        except Exception as e:
            logger.error("SQS poll error: %s", e)
        await asyncio.sleep(1)


async def _s3_poll_loop(bucket: str, prefix: str, interval: int):
    """Polling fallback — lists bucket every N seconds for new objects."""
    logger.info("Starting S3 polling: s3://%s/%s every %ds", bucket, prefix, interval)
    while True:
        try:
            objects = await object_store.list_new_objects(prefix=prefix)
            for obj in objects:
                key = obj["key"]
                if key not in _processed_keys:
                    _processed_keys.add(key)
                    asyncio.create_task(_download_and_ingest(key))
        except Exception as e:
            logger.error("S3 poll error: %s", e)
        await asyncio.sleep(interval)


def register(mcp: FastMCP):

    @mcp.tool()
    async def watch_s3_bucket(
        bucket: str = "",
        prefix: str = "",
        poll_interval_seconds: int = 60,
        use_sqs: bool = False,
    ) -> dict:
        """
        Start watching an AWS S3 bucket for new files.
        When a new file is uploaded to the bucket/prefix, automatically
        downloads it and triggers the appropriate ingestion pipeline
        (ingest_pdf, ingest_excel, ocr_document, or parse_pid).

        Two modes:
        - SQS mode (recommended): Reads S3 event notifications from SQS queue.
          Requires SQS_QUEUE_URL env var and S3→SQS event notification configured.
        - Polling mode (fallback): Lists the bucket every poll_interval_seconds.

        Args:
            bucket: S3 bucket name (defaults to S3_BUCKET env var).
            prefix: Key prefix to filter (e.g., 'uploads/', '' for all).
            poll_interval_seconds: How often to poll in polling mode.
            use_sqs: If True, use SQS event mode instead of polling.

        Returns:
            Status, watcher mode, and configuration details.
        """
        global _s3_watcher_task

        target_bucket = bucket or S3_BUCKET
        if not target_bucket:
            return {"error": "S3 bucket not configured. Set S3_BUCKET env var or pass bucket parameter."}

        if _s3_watcher_task and not _s3_watcher_task.done():
            return {"status": "already_watching", "bucket": target_bucket}

        if use_sqs and SQS_QUEUE_URL:
            _s3_watcher_task = asyncio.create_task(_sqs_poll_loop(SQS_QUEUE_URL))
            mode = "sqs"
        else:
            _s3_watcher_task = asyncio.create_task(
                _s3_poll_loop(target_bucket, prefix, poll_interval_seconds)
            )
            mode = "polling"

        return {
            "status": "watching",
            "bucket": target_bucket,
            "prefix": prefix or "(all objects)",
            "mode": mode,
            "poll_interval_seconds": poll_interval_seconds if mode == "polling" else None,
            "sqs_queue": SQS_QUEUE_URL if mode == "sqs" else None,
            "message": (
                "S3 watcher active. Drop files into the bucket to trigger ingestion automatically."
            ),
        }
