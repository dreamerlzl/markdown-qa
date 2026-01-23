"""Tests for query handler."""

from unittest.mock import MagicMock, patch

import pytest

from markdown_qa.index_manager import IndexManager
from markdown_qa.messages import MessageType
from markdown_qa.query_handler import QueryHandler


class TestQueryHandler:
    """Test query handler."""

    def test_handle_query_when_not_ready(self):
        """Test handling query when server is not ready."""
        index_manager = MagicMock(spec=IndexManager)
        index_manager.is_ready.return_value = False

        handler = QueryHandler(index_manager)
        response = handler.handle_query({"type": MessageType.QUERY, "question": "Test?"})

        assert response["type"] == MessageType.ERROR
        assert "not ready" in response["message"].lower()

    def test_handle_query_empty_question(self):
        """Test handling query with empty question."""
        index_manager = MagicMock(spec=IndexManager)
        index_manager.is_ready.return_value = True

        handler = QueryHandler(index_manager)
        response = handler.handle_query({"type": MessageType.QUERY, "question": ""})

        assert response["type"] == MessageType.ERROR
        assert "empty" in response["message"].lower()

    def test_handle_query_no_index(self):
        """Test handling query when no index is available."""
        index_manager = MagicMock(spec=IndexManager)
        index_manager.is_ready.return_value = True
        index_manager.get_index.return_value = None

        handler = QueryHandler(index_manager)
        response = handler.handle_query({"type": MessageType.QUERY, "question": "Test?"})

        assert response["type"] == MessageType.ERROR
        assert "no index" in response["message"].lower()

    def test_handle_query_success(self):
        """Test successful query handling."""
        index_manager = MagicMock(spec=IndexManager)
        index_manager.is_ready.return_value = True
        
        mock_vector_store = MagicMock()
        index_manager.get_index.return_value = mock_vector_store

        # Mock the Q&A components
        with patch("markdown_qa.query_handler.EmbeddingGenerator") as mock_emb, \
             patch("markdown_qa.query_handler.RetrievalEngine") as mock_ret, \
             patch("markdown_qa.query_handler.QuestionAnswerer") as mock_qa, \
             patch("markdown_qa.query_handler.ResponseFormatter") as mock_fmt:
            
            mock_answerer = MagicMock()
            # Mock the new separate methods used by handle_query
            mock_answerer.retrieve.return_value = (
                "Retrieved context",
                ["/path/to/doc.md"],
            )
            mock_answerer._build_prompt.return_value = "Formatted prompt"
            mock_answerer._generate_answer.return_value = "Answer text"
            mock_qa.return_value = mock_answerer
            
            mock_formatter = MagicMock()
            mock_formatter.format_response.return_value = {
                "answer": "Answer text",
                "sources": ["/path/to/doc.md"],
            }
            mock_fmt.return_value = mock_formatter

            handler = QueryHandler(index_manager)
            response = handler.handle_query({"type": MessageType.QUERY, "question": "Test?"})

            assert response["type"] == MessageType.RESPONSE
            assert "answer" in response
            assert "sources" in response
