"""Retrieval module for finding relevant chunks."""

from typing import Any, Dict, List, Tuple

from markdown_qa.embeddings import EmbeddingGenerator
from markdown_qa.vector_store import VectorStore


class RetrievalEngine:
    """Engine for retrieving relevant chunks from vector store."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_generator: EmbeddingGenerator,
    ):
        """
        Initialize retrieval engine.

        Args:
            vector_store: Vector store instance.
            embedding_generator: Embedding generator instance.
        """
        self.vector_store = vector_store
        self.embedding_generator = embedding_generator

    def retrieve(
        self, query: str, k: int = 5
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: Query string.
            k: Number of results to return.

        Returns:
            List of tuples containing (text, metadata, distance) for each result.
        """
        # Generate embedding for query
        query_embedding = self.embedding_generator.generate_embedding(query)

        # Search vector store (returns text, metadata, distance)
        results = self.vector_store.search(query_embedding, k=k)

        return results
