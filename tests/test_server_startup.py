"""Tests for server startup resilience."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from markdown_qa.server import MarkdownQAServer
from markdown_qa.server_config import ServerConfig


def _mock_api_config() -> object:
    """Create a minimal API config object for server tests."""
    return type("MockAPIConfig", (), {
        "base_url": "https://api.example.com/v1",
        "api_key": "test-key",
    })()


class _MockWebSocketServer:
    """Minimal async server compatible with MarkdownQAServer.start()."""

    async def serve_forever(self) -> None:
        await asyncio.Event().wait()


@pytest.fixture(autouse=True)
def mock_loggers():
    """Mock loggers used by server and server config."""
    with patch("markdown_qa.server.get_server_logger", return_value=MagicMock()), \
         patch("markdown_qa.server_config.get_server_logger", return_value=MagicMock()):
        yield


@pytest.mark.asyncio
async def test_start_succeeds_with_no_directories():
    """Server should start serving even when no directories are configured."""
    config = ServerConfig(directories=[], api_config=_mock_api_config())
    server = MarkdownQAServer(config)
    mock_ws_server = _MockWebSocketServer()

    mock_scheduler = MagicMock()
    mock_scheduler.start = MagicMock()
    mock_scheduler.stop = MagicMock()
    mock_scheduler.is_reloading.return_value = False

    with patch.object(server.config, "get_config_file_path", return_value=None), \
         patch("markdown_qa.server.ReloadScheduler", return_value=mock_scheduler), \
         patch("markdown_qa.server.websockets.serve", AsyncMock(return_value=mock_ws_server)) as mock_serve, \
         patch.object(server.index_manager, "load_index") as mock_load_index:
        start_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.01)
        server._shutdown_event.set()
        await start_task

    mock_load_index.assert_not_called()
    mock_serve.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_succeeds_when_index_loading_fails():
    """Server should still start serving when initial index loading fails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()

        config = ServerConfig(directories=[str(docs_dir)], api_config=_mock_api_config())
        server = MarkdownQAServer(config)
        mock_ws_server = _MockWebSocketServer()

        mock_scheduler = MagicMock()
        mock_scheduler.start = MagicMock()
        mock_scheduler.stop = MagicMock()
        mock_scheduler.is_reloading.return_value = False

        with patch.object(server.config, "get_config_file_path", return_value=None), \
             patch("markdown_qa.server.ReloadScheduler", return_value=mock_scheduler), \
             patch("markdown_qa.server.websockets.serve", AsyncMock(return_value=mock_ws_server)) as mock_serve, \
             patch.object(server.index_manager, "load_index", side_effect=RuntimeError("index failed")), \
             patch.object(server.index_manager, "is_ready", return_value=False):
            start_task = asyncio.create_task(server.start())
            await asyncio.sleep(0.01)
            server._shutdown_event.set()
            await start_task

        mock_serve.assert_awaited_once()
