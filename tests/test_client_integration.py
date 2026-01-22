"""Integration tests for CLI client with server."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from markdown_qa.client import MarkdownQAClient
from markdown_qa.messages import MessageType


class TestClientIntegration:
    """Integration tests for CLI client with server."""

    @pytest.mark.asyncio
    async def test_end_to_end_query_flow(self):
        """Test end-to-end query flow: connect → query → response."""
        client = MarkdownQAClient(server_url="ws://localhost:8765")

        # Mock WebSocket connection and messages
        mock_ws = AsyncMock()

        # Mock status response
        status_response = json.dumps({
            "type": MessageType.STATUS,
            "status": "ready",
            "message": "Server ready",
        })

        # Mock query response
        query_response = json.dumps({
            "type": MessageType.RESPONSE,
            "answer": "Python is a programming language.",
            "sources": ["/path/to/doc.md"],
        })

        # Set up recv to return status first, then query response
        mock_ws.recv.side_effect = [status_response, query_response]

        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("markdown_qa.client.websockets.connect", return_value=mock_context):
            # Connect
            connected = await client.connect()
            assert connected is True

            # Get status
            status = await client.get_status()
            assert status["status"] == "ready"

            # Send query
            response = await client.send_query("What is Python?")
            assert response["type"] == MessageType.RESPONSE
            assert "Python is a programming language" in response["answer"]

            # Disconnect
            await client.disconnect()

    @pytest.mark.asyncio
    async def test_error_handling_server_unavailable(self):
        """Test error handling when server is unavailable."""
        client = MarkdownQAClient()

        with patch("markdown_qa.client.websockets.connect") as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError("Connection refused")

            result = await client.run_single_query("Question?")

            assert result == 1  # Error exit code

    @pytest.mark.asyncio
    async def test_error_handling_invalid_response(self):
        """Test error handling with invalid JSON response."""
        client = MarkdownQAClient()
        mock_ws = AsyncMock()
        client.websocket = mock_ws

        # Mock invalid JSON response
        mock_ws.recv.return_value = "invalid json"

        with pytest.raises(RuntimeError, match="Invalid response"):
            await client.send_query("Question?")

    @pytest.mark.asyncio
    async def test_error_handling_connection_closed(self):
        """Test error handling when connection is closed."""
        client = MarkdownQAClient()
        mock_ws = AsyncMock()
        client.websocket = mock_ws

        # Mock connection closed error
        from websockets.exceptions import ConnectionClosed
        mock_ws.recv.side_effect = ConnectionClosed(None, None)

        with pytest.raises(RuntimeError, match="Connection closed"):
            await client.send_query("Question?")

    @pytest.mark.asyncio
    async def test_custom_server_url(self):
        """Test connecting to custom server URL."""
        custom_url = "ws://example.com:9000"
        client = MarkdownQAClient(server_url=custom_url)

        mock_ws = AsyncMock()
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("markdown_qa.client.websockets.connect", return_value=mock_context) as mock_connect:
            await client.connect()

            mock_connect.assert_called_once_with(custom_url)
