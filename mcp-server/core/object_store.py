"""
Object storage client — AWS S3 (primary).

Raw documents are uploaded here after ingestion so they are permanently
stored and accessible for re-processing or auditing.

Configuration (set in .env):
    AWS_ACCESS_KEY_ID       Your AWS IAM access key
    AWS_SECRET_ACCESS_KEY   Your AWS IAM secret key
    AWS_DEFAULT_REGION      e.g. ap-south-1
    S3_BUCKET               Bucket name, e.g. industreak-raw-assets
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger("ikp.s3")

# ── Config ────────────────────────────────────────────────────────────────────
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION     = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
S3_BUCKET      = os.getenv("S3_BUCKET", "industreak-raw-assets")

_client: Any = None


def _get_s3():
    """Return (or create) a boto3 S3 client using AWS credentials from env."""
    global _client
    if _client is not None:
        return _client

    if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
        raise EnvironmentError(
            "AWS credentials not found. "
            "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in your .env file.\n"
            "See .env.example for the required variable names."
        )

    _client = boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
    )
    return _client


def reset_client() -> None:
    """Force-recreate the S3 client (useful after credential rotation in tests)."""
    global _client
    _client = None


# ── Public API ────────────────────────────────────────────────────────────────

async def upload_file(local_path: str, doc_id: str, metadata: dict | None = None) -> str:
    """
    Upload a raw file to S3 and return the full S3 URI (s3://bucket/key).

    The key format is: {doc_type}/{doc_id}{ext}
    e.g.  pdf/abc123.pdf  or  excel/xyz789.xlsx
    """
    loop = asyncio.get_event_loop()
    ext = Path(local_path).suffix
    doc_type = (metadata or {}).get("doc_type", "general")
    key = f"{doc_type}/{doc_id}{ext}"

    def _run() -> str:
        s3 = _get_s3()
        extra: dict = {}
        if metadata:
            extra["Metadata"] = {str(k): str(v) for k, v in metadata.items()}
        s3.upload_file(local_path, S3_BUCKET, key, ExtraArgs=extra if extra else None)
        return key

    s3_key = await loop.run_in_executor(None, _run)
    logger.info("Uploaded %s → s3://%s/%s", local_path, S3_BUCKET, s3_key)
    return f"s3://{S3_BUCKET}/{s3_key}"


async def get_presigned_url(doc_id: str, doc_type: str = "general", ext: str = ".pdf") -> str:
    """
    Generate a 1-hour presigned GET URL for a stored document.
    The URL allows temporary download without requiring AWS credentials.
    """
    loop = asyncio.get_event_loop()
    key = f"{doc_type}/{doc_id}{ext}"

    def _run() -> str:
        s3 = _get_s3()
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=3600,
        )

    return await loop.run_in_executor(None, _run)


async def list_new_objects(prefix: str = "", since_key: str | None = None) -> list[dict]:
    """
    List objects in the configured S3 bucket.

    Args:
        prefix:    Optional key prefix filter (e.g. "pdf/" or "uploads/").
        since_key: Unused — timestamp filtering is handled inside s3_watcher.py.

    Returns:
        List of dicts with keys: key, size, last_modified.
    """
    loop = asyncio.get_event_loop()

    def _run() -> list[dict]:
        s3 = _get_s3()
        kwargs: dict[str, Any] = {"Bucket": S3_BUCKET}
        if prefix:
            kwargs["Prefix"] = prefix

        results: list[dict] = []
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(**kwargs):
            for obj in page.get("Contents", []):
                results.append({
                    "key":           obj["Key"],
                    "size":          obj["Size"],
                    "last_modified": str(obj["LastModified"]),
                })
        return results

    return await loop.run_in_executor(None, _run)


async def delete_object(key: str) -> bool:
    """Delete an object from S3. Returns True on success."""
    loop = asyncio.get_event_loop()

    def _run() -> bool:
        try:
            _get_s3().delete_object(Bucket=S3_BUCKET, Key=key)
            return True
        except ClientError as exc:
            logger.error("S3 delete failed for %s: %s", key, exc)
            return False

    return await loop.run_in_executor(None, _run)
