"""Tests for WebSocket message protocol."""

import pytest

from markdown_qa.messages import (
    MessageType,
    create_error_message,
    create_query_message,
    create_response_message,
    create_status_message,
    validate_query_message,
)


class TestMessages:
    """Test WebSocket message protocol."""

    def test_create_query_message(self):
        """Test creating a query message."""
        msg = create_query_message("What is Python?")
        assert msg["type"] == MessageType.QUERY
        assert msg["question"] == "What is Python?"

    def test_create_query_message_with_index(self):
        """Test creating a query message with index."""
        msg = create_query_message("What is Python?", index="custom")
        assert msg["type"] == MessageType.QUERY
        assert msg["question"] == "What is Python?"
        assert msg["index"] == "custom"

    def test_create_response_message(self):
        """Test creating a response message."""
        sources = ["/path/to/doc.md"]
        msg = create_response_message("Python is a language.", sources)
        assert msg["type"] == MessageType.RESPONSE
        assert msg["answer"] == "Python is a language."
        assert msg["sources"] == sources

    def test_create_error_message(self):
        """Test creating an error message."""
        msg = create_error_message("Something went wrong")
        assert msg["type"] == MessageType.ERROR
        assert msg["message"] == "Something went wrong"

    def test_create_status_message_ready(self):
        """Test creating a ready status message."""
        msg = create_status_message("ready", "Server ready")
        assert msg["type"] == MessageType.STATUS
        assert msg["status"] == "ready"
        assert msg["message"] == "Server ready"

    def test_create_status_message_without_message(self):
        """Test creating a status message without optional message."""
        msg = create_status_message("indexing")
        assert msg["type"] == MessageType.STATUS
        assert msg["status"] == "indexing"
        assert "message" not in msg

    def test_validate_query_message_valid(self):
        """Test validating a valid query message."""
        msg = {"type": MessageType.QUERY, "question": "What is Python?"}
        is_valid, error = validate_query_message(msg)
        assert is_valid is True
        assert error is None

    def test_validate_query_message_invalid_type(self):
        """Test validating query message with invalid type."""
        msg = {"type": "invalid", "question": "What is Python?"}
        is_valid, error = validate_query_message(msg)
        assert is_valid is False
        assert error is not None

    def test_validate_query_message_missing_question(self):
        """Test validating query message without question."""
        msg = {"type": MessageType.QUERY}
        is_valid, error = validate_query_message(msg)
        assert is_valid is False
        assert "question" in error.lower() if error else False

    def test_validate_query_message_empty_question(self):
        """Test validating query message with empty question."""
        msg = {"type": MessageType.QUERY, "question": ""}
        is_valid, error = validate_query_message(msg)
        assert is_valid is False
        assert error is not None

    def test_validate_query_message_not_dict(self):
        """Test validating non-dictionary message."""
        is_valid, error = validate_query_message("not a dict")
        assert is_valid is False
        assert error is not None
