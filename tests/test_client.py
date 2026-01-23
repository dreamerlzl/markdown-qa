"""Tests for CLI client module."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from markdown_qa.client import MarkdownQAClient
from markdown_qa.messages import MessageType


class TestMarkdownQAClient:
    """Test CLI client."""

    def test_init_default_server(self):
        """Test client initialization with default server."""
        client = MarkdownQAClient()
        assert client.server_url == "ws://localhost:8765"
        assert client.websocket is None

    def test_init_custom_server(self):
        """Test client initialization with custom server."""
        client = MarkdownQAClient(server_url="ws://example.com:9000")
        assert client.server_url == "ws://example.com:9000"

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        client = MarkdownQAClient()

        mock_ws = AsyncMock()
        mock_context = MagicMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        with patch("markdown_qa.client.websockets.connect", return_value=mock_context):
            result = await client.connect()

            assert result is True
            assert client.websocket == mock_ws

    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure."""
        client = MarkdownQAClient()

        with patch("markdown_qa.client.websockets.connect") as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError("Connection refused")

            result = await client.connect()

            assert result is False
            assert client.websocket is None

    @pytest.mark.asyncio
    async def test_send_query(self):
        """Test sending a query."""
        client = MarkdownQAClient()
        mock_ws = AsyncMock()
        client.websocket = mock_ws

        # Mock response
        response_data = {
            "type": MessageType.RESPONSE,
            "answer": "Python is a language.",
            "sources": [],
        }
        mock_ws.recv.return_value = json.dumps(response_data)

        response = await client.send_query("What is Python?")

        assert response["type"] == MessageType.RESPONSE
        assert response["answer"] == "Python is a language."
        mock_ws.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_query_with_index(self):
        """Test sending a query with index."""
        client = MarkdownQAClient()
        mock_ws = AsyncMock()
        client.websocket = mock_ws

        response_data = {"type": MessageType.RESPONSE, "answer": "Answer", "sources": []}
        mock_ws.recv.return_value = json.dumps(response_data)

        await client.send_query("Question?", index="custom")

        # Verify index was included in message
        call_args = mock_ws.send.call_args[0][0]
        message = json.loads(call_args)
        assert message["index"] == "custom"

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test getting server status."""
        client = MarkdownQAClient()
        mock_ws = AsyncMock()
        client.websocket = mock_ws

        status_data = {"type": MessageType.STATUS, "status": "ready"}
        mock_ws.recv.return_value = json.dumps(status_data)

        status = await client.get_status()

        assert status["type"] == MessageType.STATUS
        assert status["status"] == "ready"

    def test_display_response_response(self, capsys):
        """Test displaying a response message."""
        client = MarkdownQAClient()
        response = {
            "type": MessageType.RESPONSE,
            "answer": "Python is a language.",
            "sources": ["/path/to/doc.md"],
        }

        client.display_response(response)

        captured = capsys.readouterr()
        assert "Python is a language." in captured.out
        assert "/path/to/doc.md" in captured.out

    def test_display_response_error(self, capsys):
        """Test displaying an error message."""
        client = MarkdownQAClient()
        response = {"type": MessageType.ERROR, "message": "Something went wrong"}

        client.display_response(response)

        captured = capsys.readouterr()
        assert "Error: Something went wrong" in captured.err

    def test_display_response_status(self, capsys):
        """Test displaying a status message."""
        client = MarkdownQAClient()
        response = {"type": MessageType.STATUS, "status": "ready", "message": "Server ready"}

        client.display_response(response)

        captured = capsys.readouterr()
        assert "Status: ready" in captured.out
        assert "Server ready" in captured.out

    @pytest.mark.asyncio
    async def test_run_single_query_success(self):
        """Test running a single query successfully."""
        client = MarkdownQAClient()

        with patch.object(client, "connect", return_value=True), \
             patch.object(client, "get_status", new=AsyncMock(return_value={"status": "ready"})), \
             patch.object(client, "send_query_stream") as mock_query_stream, \
             patch.object(client, "disconnect") as mock_disconnect:

            mock_query_stream.return_value = {
                "type": MessageType.RESPONSE,
                "answer": "Answer",
                "sources": [],
            }

            result = await client.run_single_query("Question?")

            assert result == 0
            mock_query_stream.assert_called_once_with("Question?", index=None)

    @pytest.mark.asyncio
    async def test_run_single_query_connection_failure(self):
        """Test single query with connection failure."""
        client = MarkdownQAClient()

        with patch.object(client, "connect", return_value=False):
            result = await client.run_single_query("Question?")

            assert result == 1

    @pytest.mark.asyncio
    async def test_run_single_query_error_response(self):
        """Test single query with error response."""
        client = MarkdownQAClient()

        with patch.object(client, "connect", return_value=True), \
             patch.object(client, "get_status", new=AsyncMock(return_value={"status": "ready"})), \
             patch.object(client, "send_query_stream") as mock_query_stream, \
             patch.object(client, "disconnect"):

            mock_query_stream.return_value = {
                "type": MessageType.ERROR,
                "message": "Error occurred",
            }

            result = await client.run_single_query("Question?")

            assert result == 1
            mock_query_stream.assert_called_once()
