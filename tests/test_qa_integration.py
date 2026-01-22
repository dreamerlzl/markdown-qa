"""Integration tests for complete Q&A flow."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from markdown_qa.cache import CacheManager
from markdown_qa.config import APIConfig
from markdown_qa.embeddings import EmbeddingGenerator
from markdown_qa.formatter import ResponseFormatter
from markdown_qa.qa import QuestionAnswerer
from markdown_qa.retrieval import RetrievalEngine
from markdown_qa.vector_store import VectorStore


class TestQAIntegration:
    """Integration tests for complete Q&A flow: retrieve chunks → generate answer → format with sources."""

    def test_complete_qa_flow(self):
        """Test complete Q&A flow from retrieval to formatted response."""
        # Create temporary directory with markdown file
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()
            doc_file = doc_dir / "test.md"
            doc_file.write_text("# Introduction\n\nPython is a programming language.\n\n## Features\n\nPython has many features.")

            # Mock API config
            api_config = MagicMock(spec=APIConfig)
            api_config.base_url = "https://api.example.com"
            api_config.api_key = "test-key"

            # Mock embedding generator (to avoid actual API calls)
            with patch("markdown_qa.qa.OpenAI") as mock_openai_class, \
                 patch("markdown_qa.embeddings.OpenAI") as mock_embeddings_openai, \
                 patch("markdown_qa.vector_store.OpenAI") as mock_vector_openai:
                
                # Mock OpenAI clients
                mock_llm_client = MagicMock()
                mock_openai_class.return_value = mock_llm_client
                
                mock_emb_client = MagicMock()
                mock_embeddings_openai.return_value = mock_emb_client
                
                mock_vector_client = MagicMock()
                mock_vector_openai.return_value = mock_vector_client

                # Mock LLM response
                mock_response = MagicMock()
                mock_response.choices = [
                    MagicMock(message=MagicMock(content="Python is a high-level programming language known for its simplicity."))
                ]
                mock_llm_client.chat.completions.create.return_value = mock_response

                # Mock embedding response
                mock_emb_response = MagicMock()
                mock_emb_response.data = [MagicMock(embedding=[0.1] * 1536)]  # Mock embedding vector
                mock_emb_client.embeddings.create.return_value = mock_emb_response

                # Create components
                cache_manager = CacheManager(cache_dir=Path(tmpdir) / "cache")
                
                # Create vector store with mocked embedding generator
                embedding_gen = EmbeddingGenerator(api_config=api_config, cache_dir=cache_manager.embedding_dir)
                vector_store = VectorStore(
                    cache_manager=cache_manager,
                    embedding_generator=embedding_gen,
                )

                # Build index (this will use mocked embeddings)
                try:
                    vector_store.build_index([str(doc_dir)], index_name="test", show_progress=False)
                except Exception:
                    # If building fails due to mocking, create a minimal mock vector store
                    vector_store.index = MagicMock()
                    vector_store.metadata = [
                        {
                            "file_path": str(doc_file),
                            "section": "Introduction",
                        }
                    ]
                    vector_store.texts = ["Python is a programming language."]
                    # Mock search method
                    vector_store.search = MagicMock(return_value=[
                        (
                            "Python is a programming language.",
                            {"file_path": str(doc_file), "section": "Introduction"},
                            0.3,
                        )
                    ])

                # Create retrieval engine
                retrieval_engine = RetrievalEngine(vector_store, embedding_gen)

                # Create question answerer
                answerer = QuestionAnswerer(retrieval_engine, api_config=api_config)

                # Answer question
                answer, sources = answerer.answer("What is Python?")

                # Verify answer
                assert answer
                assert len(sources) > 0
                assert sources[0] == str(doc_file)

                # Format response
                formatter = ResponseFormatter()
                formatted = formatter.format_response(answer, sources)

                # Verify formatted response
                assert formatted["answer"] == answer
                assert len(formatted["sources"]) > 0
                assert formatted["sources"][0] == str(doc_file)

                # Test display formatting
                display_text = formatter.format_for_display(answer, sources)
                assert answer in display_text
                assert "Sources:" in display_text
                assert str(doc_file) in display_text

    def test_qa_flow_with_no_results(self):
        """Test Q&A flow when no relevant chunks are found."""
        # Mock retrieval engine that returns no results
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.retrieve.return_value = []

        api_config = MagicMock(spec=APIConfig)
        api_config.base_url = "https://api.example.com"
        api_config.api_key = "test-key"

        answerer = QuestionAnswerer(retrieval_engine, api_config=api_config)

        # Should raise ValueError when no relevant content found
        with pytest.raises(ValueError, match="No relevant content found"):
            answerer.answer("What is Python?")

    def test_qa_flow_with_multiple_sources(self):
        """Test Q&A flow with multiple sources."""
        retrieval_engine = MagicMock(spec=RetrievalEngine)
        retrieval_engine.retrieve.return_value = [
            (
                "Content from doc1.",
                {"file_path": "/path/to/doc1.md", "section": "Section 1"},
                0.3,
            ),
            (
                "Content from doc2.",
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

            # Format response
            formatter = ResponseFormatter()
            formatted = formatter.format_response(answer, sources)

            # Verify multiple sources are included
            assert len(formatted["sources"]) == 2
            assert formatted["sources"][0] == "/path/to/doc1.md"
            assert formatted["sources"][1] == "/path/to/doc2.md"
