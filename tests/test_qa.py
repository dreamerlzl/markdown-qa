"""Tests for question answering module."""

from unittest.mock import MagicMock, patch

import pytest

from markdown_qa.config import APIConfig
from markdown_qa.qa import QuestionAnswerer
from markdown_qa.retrieval import RetrievalEngine


class TestQuestionAnswerer:
    """Test question answering with LLM integration."""

    def test_answer_with_relevant_content(self):
        """Test answering a question with relevant content."""
        # Mock retrieval engine
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.retrieve.return_value = [
            (
                "Python is a programming language.",
                {"file_path": "/path/to/doc.md", "section": "Introduction"},
                0.5,
            )
        ]

        # Mock API config
        api_config = MagicMock(spec=APIConfig)
        api_config.base_url = "https://api.example.com"
        api_config.api_key = "test-key"

        # Mock OpenAI client
        with patch("markdown_qa.qa.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="Python is a high-level programming language."))
            ]
            mock_client.chat.completions.create.return_value = mock_response

            answerer = QuestionAnswerer(retrieval_engine, api_config=api_config)
            answer, sources = answerer.answer("What is Python?")

            assert answer == "Python is a high-level programming language."
            assert len(sources) == 1
            assert sources[0] == "/path/to/doc.md"

    def test_answer_with_no_relevant_content(self):
        """Test answering when no relevant content is found."""
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.retrieve.return_value = []

        api_config = MagicMock(spec=APIConfig)
        api_config.base_url = "https://api.example.com"
        api_config.api_key = "test-key"

        answerer = QuestionAnswerer(retrieval_engine, api_config=api_config)

        with pytest.raises(ValueError, match="No relevant content found"):
            answerer.answer("What is Python?")

    def test_answer_filters_by_relevance_threshold(self):
        """Test that answers filter chunks by relevance threshold."""
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.retrieve.return_value = [
            (
                "Relevant content.",
                {"file_path": "/path/to/doc.md", "section": "Section"},
                0.3,  # Low distance = high relevance
            ),
            (
                "Less relevant content.",
                {"file_path": "/path/to/doc2.md", "section": "Section"},
                0.9,  # High distance = low relevance
            ),
        ]

        api_config = MagicMock(spec=APIConfig)
        api_config.base_url = "https://api.example.com"
        api_config.api_key = "test-key"

        with patch("markdown_qa.qa.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="Answer based on relevant content."))
            ]
            mock_client.chat.completions.create.return_value = mock_response

            answerer = QuestionAnswerer(retrieval_engine, api_config=api_config)
            # Set threshold to filter out low-relevance chunks
            answer, sources = answerer.answer("Question?", min_relevance_threshold=0.5)

            # Should only include the relevant chunk (distance 0.3 < 0.5)
            assert len(sources) == 1
            assert sources[0] == "/path/to/doc.md"

    def test_answer_includes_multiple_sources(self):
        """Test that answer includes multiple sources when available."""
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.retrieve.return_value = [
            (
                "Content 1.",
                {"file_path": "/path/to/doc1.md", "section": "Section 1"},
                0.3,
            ),
            (
                "Content 2.",
                {"file_path": "/path/to/doc2.md", "section": "Section 2"},
                0.4,
            ),
        ]

        api_config = MagicMock(spec=APIConfig)
        api_config.base_url = "https://api.example.com"
        api_config.api_key = "test-key"

        with patch("markdown_qa.qa.OpenAI") as mock_openai_class:
            mock_client = MagicMock()
            mock_openai_class.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [
                MagicMock(message=MagicMock(content="Answer using multiple sources."))
            ]
            mock_client.chat.completions.create.return_value = mock_response

            answerer = QuestionAnswerer(retrieval_engine, api_config=api_config)
            answer, sources = answerer.answer("Question?", k=2)

            assert len(sources) == 2
            assert sources[0] == "/path/to/doc1.md"
            assert sources[1] == "/path/to/doc2.md"

    def test_build_prompt_includes_context(self):
        """Test that prompt includes retrieved context."""
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        api_config = MagicMock(spec=APIConfig)
        api_config.base_url = "https://api.example.com"
        api_config.api_key = "test-key"

        answerer = QuestionAnswerer(retrieval_engine, api_config=api_config)
        prompt = answerer._build_prompt("What is Python?", "Python is a language.")

        assert "What is Python?" in prompt
        assert "Python is a language." in prompt
        assert "Context from documentation:" in prompt
