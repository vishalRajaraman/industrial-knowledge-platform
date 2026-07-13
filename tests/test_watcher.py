"""
Tests for Component 2.1: Local & Cloud File Watcher

Run with:
    cd industrial-knowledge-platform
    pip install pytest pytest-asyncio watchdog
    pytest tests/test_watcher.py -v

These tests use real temporary directories and mock the ingestion tools
so no actual PDF/Excel processing or S3 calls are made.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_dummy_file(folder: Path, filename: str = "test_document.pdf") -> Path:
    """Create a non-empty dummy file in the given folder."""
    p = folder / filename
    p.write_bytes(b"%PDF-1.4 dummy content for testing")
    return p


# ═══════════════════════════════════════════════════════════════════════════════
# 1. LOCAL WATCHER (watcher.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLocalWatcher:
    """Tests for the watchdog-based local folder watcher."""

    @pytest.mark.asyncio
    async def test_watch_nonexistent_folder_auto_creates(self, tmp_path):
        """watch_local_folder should auto-create the target folder if missing."""
        from mcp_server.tools.ingestion import watcher  # noqa: F401 — ensure clean import

        new_folder = tmp_path / "new_watch_dir"
        assert not new_folder.exists()

        # Patch _process_file so no real ingestion happens
        with patch("tools.ingestion.watcher._process_file", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = {"status": "ok"}

            # Dynamically import register and build a minimal fake MCP
            from tools.ingestion.watcher import register, _active_watchers
            _active_watchers.clear()

            registered_tools: dict = {}

            class FakeMCP:
                def tool(self):
                    def decorator(fn):
                        registered_tools[fn.__name__] = fn
                        return fn
                    return decorator

            register(FakeMCP())
            result = await registered_tools["watch_local_folder"](
                folder_path=str(new_folder),
                scan_existing=False,
            )

        assert new_folder.exists(), "Folder should have been auto-created"
        assert result["status"] == "watching"
        assert result["folder"] == str(new_folder.resolve())

        # Cleanup
        _active_watchers.clear()

    @pytest.mark.asyncio
    async def test_watch_already_watching_returns_status(self, tmp_path):
        """Calling watch_local_folder twice on the same folder returns already_watching."""
        from tools.ingestion.watcher import register, _active_watchers
        _active_watchers.clear()

        registered_tools: dict = {}

        class FakeMCP:
            def tool(self):
                def decorator(fn):
                    registered_tools[fn.__name__] = fn
                    return fn
                return decorator

        register(FakeMCP())

        with patch("tools.ingestion.watcher._process_file", new_callable=AsyncMock):
            r1 = await registered_tools["watch_local_folder"](
                folder_path=str(tmp_path), scan_existing=False
            )
            r2 = await registered_tools["watch_local_folder"](
                folder_path=str(tmp_path), scan_existing=False
            )

        assert r1["status"] == "watching"
        assert r2["status"] == "already_watching"
        _active_watchers.clear()

    @pytest.mark.asyncio
    async def test_scan_existing_ingests_pre_existing_files(self, tmp_path):
        """scan_existing=True should immediately queue pre-existing supported files."""
        _write_dummy_file(tmp_path, "existing.pdf")
        _write_dummy_file(tmp_path, "notes.xlsx")
        (tmp_path / "readme.txt").write_text("ignored")  # unsupported extension

        ingested: list[str] = []

        async def fake_process(path: str):
            ingested.append(path)
            return {"status": "ok"}

        from tools.ingestion.watcher import register, _active_watchers
        _active_watchers.clear()

        registered_tools: dict = {}

        class FakeMCP:
            def tool(self):
                def decorator(fn):
                    registered_tools[fn.__name__] = fn
                    return fn
                return decorator

        register(FakeMCP())

        with patch("tools.ingestion.watcher._process_file", side_effect=fake_process):
            result = await registered_tools["watch_local_folder"](
                folder_path=str(tmp_path), scan_existing=True
            )

        # Allow async tasks to run
        await asyncio.sleep(0.1)

        assert result["initial_files_queued"] == 2
        # .txt should not be queued
        assert all(p.endswith((".pdf", ".xlsx")) for p in ingested)
        _active_watchers.clear()

    @pytest.mark.asyncio
    async def test_stop_watching_folder(self, tmp_path):
        """stop_watching_folder should cleanly cancel the watcher."""
        from tools.ingestion.watcher import register, _active_watchers
        _active_watchers.clear()

        registered_tools: dict = {}

        class FakeMCP:
            def tool(self):
                def decorator(fn):
                    registered_tools[fn.__name__] = fn
                    return fn
                return decorator

        register(FakeMCP())

        with patch("tools.ingestion.watcher._process_file", new_callable=AsyncMock):
            await registered_tools["watch_local_folder"](
                folder_path=str(tmp_path), scan_existing=False
            )
            folder_str = str(tmp_path.resolve())
            assert folder_str in _active_watchers

            result = await registered_tools["stop_watching_folder"](folder_path=str(tmp_path))

        assert result["status"] == "stopped"
        assert folder_str not in _active_watchers

    @pytest.mark.asyncio
    async def test_list_active_watchers(self, tmp_path):
        """list_active_watchers should report all active watchers."""
        from tools.ingestion.watcher import register, _active_watchers
        _active_watchers.clear()

        registered_tools: dict = {}

        class FakeMCP:
            def tool(self):
                def decorator(fn):
                    registered_tools[fn.__name__] = fn
                    return fn
                return decorator

        register(FakeMCP())

        with patch("tools.ingestion.watcher._process_file", new_callable=AsyncMock):
            await registered_tools["watch_local_folder"](
                folder_path=str(tmp_path), scan_existing=False
            )
            result = await registered_tools["list_active_watchers"]()

        assert result["total"] == 1
        assert result["local_watchers"][0]["active"] is True
        _active_watchers.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. S3 WATCHER STATE PERSISTENCE (s3_watcher.py)
# ═══════════════════════════════════════════════════════════════════════════════

class TestS3WatcherState:
    """Tests for the timestamp-based state persistence in s3_watcher.py."""

    def test_load_state_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        """_load_state() returns empty defaults if the state file does not exist."""
        import tools.ingestion.s3_watcher as sw
        monkeypatch.setattr(sw, "_STATE_FILE", tmp_path / "no_file.json")

        state = sw._load_state()
        assert state == {"last_checked": None, "processed_keys": []}

    def test_save_and_load_state_roundtrip(self, tmp_path, monkeypatch):
        """State written by _save_state() is correctly read back by _load_state()."""
        import tools.ingestion.s3_watcher as sw
        monkeypatch.setattr(sw, "_STATE_FILE", tmp_path / "state.json")

        test_state = {
            "last_checked": "2025-01-01T00:00:00+00:00",
            "processed_keys": ["uploads/doc1.pdf", "uploads/doc2.xlsx"],
        }
        sw._save_state(test_state)
        loaded = sw._load_state()

        assert loaded["last_checked"] == test_state["last_checked"]
        assert set(loaded["processed_keys"]) == set(test_state["processed_keys"])

    def test_save_state_handles_corrupt_file_gracefully(self, tmp_path, monkeypatch):
        """_load_state() returns defaults if the state file is corrupt JSON."""
        import tools.ingestion.s3_watcher as sw
        state_file = tmp_path / "corrupt.json"
        state_file.write_text("NOT VALID JSON {{{{")
        monkeypatch.setattr(sw, "_STATE_FILE", state_file)

        state = sw._load_state()
        assert state["last_checked"] is None

    @pytest.mark.asyncio
    async def test_reset_s3_watcher_state_deletes_file(self, tmp_path, monkeypatch):
        """reset_s3_watcher_state should delete the state file."""
        import tools.ingestion.s3_watcher as sw
        state_file = tmp_path / "state.json"
        state_file.write_text('{"last_checked": "2025-01-01", "processed_keys": []}')
        monkeypatch.setattr(sw, "_STATE_FILE", state_file)

        registered_tools: dict = {}

        class FakeMCP:
            def tool(self):
                def decorator(fn):
                    registered_tools[fn.__name__] = fn
                    return fn
                return decorator

        sw.register(FakeMCP())
        result = await registered_tools["reset_s3_watcher_state"]()

        assert not state_file.exists()
        assert result["status"] == "reset"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. OBJECT STORE (object_store.py) — no MinIO
# ═══════════════════════════════════════════════════════════════════════════════

class TestObjectStore:
    """Tests for the stripped-down AWS-only object_store.py."""

    def test_get_s3_raises_without_credentials(self, monkeypatch):
        """_get_s3() must raise EnvironmentError if AWS keys are not set."""
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

        import importlib
        import tools.ingestion  # noqa
        import core.object_store as obj
        importlib.reload(obj)  # re-read env vars after monkeypatch

        obj.reset_client()
        with pytest.raises(EnvironmentError, match="AWS credentials not found"):
            obj._get_s3()

    def test_no_minio_imports_in_object_store(self):
        """Ensure object_store.py contains no references to MinIO."""
        src = Path(__file__).parent.parent / "mcp-server" / "core" / "object_store.py"
        code = src.read_text(encoding="utf-8").lower()
        assert "minio" not in code, "object_store.py should not reference MinIO"

    def test_no_minio_imports_in_watcher(self):
        """Ensure watcher.py contains no references to MinIO."""
        src = Path(__file__).parent.parent / "mcp-server" / "tools" / "ingestion" / "watcher.py"
        code = src.read_text(encoding="utf-8").lower()
        assert "minio" not in code, "watcher.py should not reference MinIO"
