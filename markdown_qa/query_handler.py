"""Query handler module for processing queries."""

from typing import Any, Dict, Generator, Optional

from markdown_qa.embeddings import EmbeddingGenerator
from markdown_qa.formatter import ResponseFormatter
from markdown_qa.index_manager import IndexManager
from markdown_qa.messages import (
    create_error_message,
    create_response_message,
    create_stream_start_message,
    create_stream_chunk_message,
    create_stream_end_message,
)
from markdown_qa.qa import QuestionAnswerer
from markdown_qa.retrieval import RetrievalEngine


class QueryHandler:
    """Handles query processing using in-memory indexes."""

    def __init__(
        self,
        index_manager: IndexManager,
        api_config: Optional[Any] = None,
    ):
        """
        Initialize query handler.

        Args:
            index_manager: Index manager instance.
            api_config: API configuration.
        """
        self.index_manager = index_manager
        self.api_config = api_config

    def handle_query(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a query message.

        Args:
            message: Query message dictionary.

        Returns:
            Response message dictionary (response or error).
        """
        # Check if server is ready
        if not self.index_manager.is_ready():
            return create_error_message(
                "Server is not ready. Indexes are still loading."
            )

        # Get question
        question = message.get("question", "").strip()
        if not question:
            return create_error_message("Question cannot be empty")

        # Get index name (optional)
        index_name = message.get("index")

        try:
            # Get current index
            vector_store = self.index_manager.get_index()
            if vector_store is None:
                return create_error_message("No index available")

            # Create retrieval engine and question answerer
            embedding_gen = EmbeddingGenerator(api_config=self.api_config)
            retrieval_engine = RetrievalEngine(vector_store, embedding_gen)
            answerer = QuestionAnswerer(retrieval_engine, api_config=self.api_config)

            # Generate answer
            answer, sources = answerer.answer(question)

            # Format response
            formatter = ResponseFormatter()
            formatted = formatter.format_response(answer, sources)

            # Return response message
            return create_response_message(formatted["answer"], formatted["sources"])

        except ValueError as e:
            # Handle "no relevant content" case
            return create_error_message(str(e))
        except Exception as e:
            # Handle other errors
            return create_error_message(f"Error processing query: {str(e)}")

    def handle_query_stream(
        self, message: Dict[str, Any]
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Handle a query message with streaming response.

        Args:
            message: Query message dictionary.

        Yields:
            Stream messages (start, chunks, end, or error).
        """
        # Check if server is ready
        if not self.index_manager.is_ready():
            yield create_error_message(
                "Server is not ready. Indexes are still loading."
            )
            return

        # Get question
        question = message.get("question", "").strip()
        if not question:
            yield create_error_message("Question cannot be empty")
            return

        try:
            # Get current index
            vector_store = self.index_manager.get_index()
            if vector_store is None:
                yield create_error_message("No index available")
                return

            # Create retrieval engine and question answerer
            embedding_gen = EmbeddingGenerator(api_config=self.api_config)
            retrieval_engine = RetrievalEngine(vector_store, embedding_gen)
            answerer = QuestionAnswerer(retrieval_engine, api_config=self.api_config)

            # Signal stream start
            yield create_stream_start_message()

            # Stream the answer
            for chunk, sources in answerer.answer_stream(question):
                if sources is not None:
                    # Final message with sources
                    yield create_stream_end_message(sources)
                elif chunk:
                    yield create_stream_chunk_message(chunk)

        except ValueError as e:
            # Handle "no relevant content" case
            yield create_error_message(str(e))
        except Exception as e:
            # Handle other errors
            yield create_error_message(f"Error processing query: {str(e)}")
