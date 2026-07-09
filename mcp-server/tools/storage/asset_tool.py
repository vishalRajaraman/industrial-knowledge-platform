"""
Storage tools — AWS S3 object storage for raw document assets.
store_raw_asset, retrieve_raw_asset.
"""
from mcp.server.fastmcp import FastMCP
from core import object_store


def register(mcp: FastMCP):

    @mcp.tool()
    async def store_raw_asset(file_path: str, doc_id: str, metadata: dict | None = None) -> dict:
        """
        Upload a raw document file to AWS S3 object storage.
        Stores the original file for source citation, rendering, and audit trail.

        S3 key structure: {doc_type}/{doc_id}{extension}
        Bucket: configured via S3_BUCKET environment variable.

        Args:
            file_path: Local path to the file to upload.
            doc_id: Unique document identifier (UUID).
            metadata: Optional metadata dict to attach as S3 object metadata.

        Returns:
            s3_url: Full S3 URL of the stored object.
        """
        s3_url = await object_store.upload_file(file_path, doc_id, metadata)
        return {"doc_id": doc_id, "s3_url": s3_url, "stored": True}

    @mcp.tool()
    async def retrieve_raw_asset(doc_id: str, doc_type: str = "general", extension: str = ".pdf") -> dict:
        """
        Generate a presigned download URL for a raw document in S3.
        URL is valid for 1 hour and can be used directly in the frontend.

        Args:
            doc_id: Document UUID.
            doc_type: Document type (used for key prefix lookup).
            extension: File extension (default: .pdf).

        Returns:
            presigned_url: Time-limited download URL for the original document.
        """
        url = await object_store.get_presigned_url(doc_id, doc_type, extension)
        return {"doc_id": doc_id, "presigned_url": url, "expires_in_seconds": 3600}

    @mcp.tool()
    async def list_s3_assets(prefix: str = "") -> dict:
        """
        List all document files in the S3 raw assets bucket.
        Optionally filter by prefix (doc_type folder).

        Args:
            prefix: Key prefix to filter (e.g., 'maintenance/', 'inspection/').

        Returns:
            List of objects with key, size, and last_modified.
        """
        objects = await object_store.list_new_objects(prefix=prefix)
        return {"objects": objects, "count": len(objects), "prefix": prefix or "(all)"}
