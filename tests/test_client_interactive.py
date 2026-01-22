"""Tests for CLI client interactive mode."""

from unittest.mock import AsyncMock, patch

import pytest

from markdown_qa.client import MarkdownQAClient
from markdown_qa.messages import MessageType


class TestClientInteractive:
    """Test CLI client interactive mode."""

    @pytest.mark.asyncio
    async def test_interactive_mode_quit(self):
        """Test interactive mode with quit command."""
        client = MarkdownQAClient()

        with patch.object(client, "connect", return_value=True), \
             patch.object(client, "get_status") as mock_status, \
             patch.object(client, "send_query") as mock_query, \
             patch.object(client, "display_response") as mock_display, \
             patch.object(client, "disconnect") as mock_disconnect, \
             patch("builtins.input", side_effect=["quit"]):

            mock_status.return_value = {
                "type": MessageType.STATUS,
                "status": "ready",
            }

            result = await client.run_interactive()

            assert result == 0
            mock_disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_interactive_mode_exit(self):
        """Test interactive mode with exit command."""
        client = MarkdownQAClient()

        with patch.object(client, "connect", return_value=True), \
             patch.object(client, "get_status"), \
             patch.object(client, "disconnect"), \
             patch("builtins.input", side_effect=["exit"]):

            result = await client.run_interactive()

            assert result == 0

    @pytest.mark.asyncio
    async def test_interactive_mode_questions(self):
        """Test interactive mode with multiple questions."""
        client = MarkdownQAClient()

        with patch.object(client, "connect", return_value=True), \
             patch.object(client, "get_status") as mock_status, \
             patch.object(client, "send_query") as mock_query, \
             patch.object(client, "display_response") as mock_display, \
             patch.object(client, "disconnect"), \
             patch("builtins.input", side_effect=["Question 1", "Question 2", "quit"]):

            mock_status.return_value = {
                "type": MessageType.STATUS,
                "status": "ready",
            }
            mock_query.return_value = {
                "type": MessageType.RESPONSE,
                "answer": "Answer",
                "sources": [],
            }

            result = await client.run_interactive()

            assert result == 0
            assert mock_query.call_count == 2
            # display_response is called for status (1) + 2 queries (2) = 3 total
            assert mock_display.call_count == 3

    @pytest.mark.asyncio
    async def test_interactive_mode_empty_question(self):
        """Test interactive mode with empty question."""
        client = MarkdownQAClient()

        with patch.object(client, "connect", return_value=True), \
             patch.object(client, "get_status"), \
             patch.object(client, "send_query") as mock_query, \
             patch.object(client, "disconnect"), \
             patch("builtins.input", side_effect=["", "quit"]):

            result = await client.run_interactive()

            assert result == 0
            # Empty question should not trigger query
            mock_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_interactive_mode_keyboard_interrupt(self):
        """Test interactive mode with keyboard interrupt."""
        client = MarkdownQAClient()

        with patch.object(client, "connect", return_value=True), \
             patch.object(client, "get_status"), \
             patch.object(client, "disconnect"), \
             patch("builtins.input", side_effect=KeyboardInterrupt()):

            result = await client.run_interactive()

            assert result == 0

    @pytest.mark.asyncio
    async def test_interactive_mode_connection_failure(self):
        """Test interactive mode with connection failure."""
        client = MarkdownQAClient()

        with patch.object(client, "connect", return_value=False):
            result = await client.run_interactive()

            assert result == 1
