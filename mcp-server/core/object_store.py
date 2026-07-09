"""
Object storage client — AWS S3 (primary) or MinIO (local fallback).
Raw documents stored in S3; S3 events trigger ingestion pipeline.
"""
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
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
S3_BUCKET = os.getenv("S3_BUCKET", "industreak-raw-assets")

# MinIO fallback for local dev
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT")   # e.g. http://localhost:9000
MINIO_ACCESS = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET = os.getenv("MINIO_SECRET_KEY")

_client = None


def _get_s3():
    global _client
    if _client is not None:
        return _client
    if MINIO_ENDPOINT:
        _client = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS or "minioadmin",
            aws_secret_access_key=MINIO_SECRET or "minioadmin",
        )
    elif AWS_ACCESS_KEY:
        _client = boto3.client(
            "s3",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
        )
    else:
        raise EnvironmentError(
            "Set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY for S3, "
            "or MINIO_ENDPOINT + MINIO_ACCESS_KEY + MINIO_SECRET_KEY for local MinIO."
        )
    return _client


async def upload_file(local_path: str, doc_id: str, metadata: dict | None = None) -> str:
    """Upload a raw file to S3/MinIO. Returns the S3 key."""
    loop = asyncio.get_event_loop()
    ext = Path(local_path).suffix
    doc_type = (metadata or {}).get("doc_type", "general")
    key = f"{doc_type}/{doc_id}{ext}"

    def _run():
        s3 = _get_s3()
        extra = {"Metadata": {str(k): str(v) for k, v in (metadata or {}).items()}}
        s3.upload_file(local_path, S3_BUCKET, key, ExtraArgs=extra)
        return key

    s3_key = await loop.run_in_executor(None, _run)
    return f"s3://{S3_BUCKET}/{s3_key}"


async def get_presigned_url(doc_id: str, doc_type: str = "general", ext: str = ".pdf") -> str:
    """Generate a 1-hour presigned download URL."""
    loop = asyncio.get_event_loop()
    key = f"{doc_type}/{doc_id}{ext}"

    def _run():
        s3 = _get_s3()
        return s3.generate_presigned_url(
            "get_object", Params={"Bucket": S3_BUCKET, "Key": key}, ExpiresIn=3600
        )

    return await loop.run_in_executor(None, _run)


async def list_new_objects(prefix: str = "", since_key: str | None = None) -> list[dict]:
    """List objects in S3 bucket (for polling-based trigger)."""
    loop = asyncio.get_event_loop()

    def _run():
        s3 = _get_s3()
        kwargs: dict[str, Any] = {"Bucket": S3_BUCKET}
        if prefix:
            kwargs["Prefix"] = prefix
        resp = s3.list_objects_v2(**kwargs)
        objects = resp.get("Contents", [])
        return [
            {"key": o["Key"], "size": o["Size"], "last_modified": str(o["LastModified"])}
            for o in objects
        ]

    return await loop.run_in_executor(None, _run)
