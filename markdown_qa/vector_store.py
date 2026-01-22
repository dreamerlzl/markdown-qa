"""Vector store initialization and document indexing using FAISS."""

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np

from markdown_qa.cache import CacheManager
from markdown_qa.chunker import MarkdownChunker
from markdown_qa.config import APIConfig
from markdown_qa.embeddings import EmbeddingGenerator
from markdown_qa.loader import load_markdown_files
from markdown_qa.logger import get_server_logger


class VectorStore:
    """Manages vector store initialization and document indexing."""

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        chunker: Optional[MarkdownChunker] = None,
        api_config: Optional[APIConfig] = None,
    ):
        """
        Initialize vector store.

        Args:
            cache_manager: Cache manager instance. If None, creates default.
            embedding_generator: Embedding generator instance. If None, creates default.
            chunker: Chunker instance. If None, creates default.
            api_config: API configuration. If None and embedding_generator is None, creates default.
        """
        self.cache_manager = cache_manager or CacheManager()
        self.embedding_generator = embedding_generator or EmbeddingGenerator(
            api_config=api_config,
            cache_dir=self.cache_manager.embedding_dir
        )
        self.chunker = chunker or MarkdownChunker()

        self.index: Optional[faiss.Index] = None  # type: ignore[possibly-missing-attribute]
        self.metadata: List[Dict[str, Any]] = []
        self.texts: List[str] = []
        self.logger = get_server_logger()

    def build_index(
        self,
        directories: List[str],
        index_name: str = "default",
        show_progress: bool = False,
    ) -> "VectorStore":
        """
        Build a vector index from markdown files in directories.

        Args:
            directories: List of directory paths containing markdown files.
            index_name: Name for the index.
            show_progress: Whether to show progress indicators.

        Returns:
            Self for method chaining.
        """
        import time

        start_time = time.time()

        # Load markdown files
        if show_progress:
            self.logger.info(f"Loading markdown files from {len(directories)} directory(ies)...")
        files = load_markdown_files(directories)

        if not files:
            raise ValueError("No markdown files found in specified directories")

        # Chunk files
        if show_progress:
            self.logger.info(f"Chunking {len(files)} markdown file(s)...")
        chunks = self.chunker.chunk_files(files)

        if not chunks:
            raise ValueError("No chunks created from markdown files")

        # Generate embeddings
        if show_progress:
            self.logger.info(f"Generating embeddings for {len(chunks)} chunk(s)...")
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedding_generator.generate_embeddings(
            texts, show_progress=show_progress
        )

        # Convert to numpy array
        embedding_dim = len(embeddings[0])
        embeddings_array = np.array(embeddings, dtype=np.float32)

        # Create FAISS index
        self.index = faiss.IndexFlatL2(embedding_dim)  # type: ignore[possibly-missing-attribute]
        self.index.add(embeddings_array)  # type: ignore[missing-argument]

        # Store metadata and texts
        self.metadata = [chunk["metadata"] for chunk in chunks]
        self.texts = [chunk["text"] for chunk in chunks]

        # Save to disk
        self.save_index(index_name)

        elapsed = time.time() - start_time
        if show_progress and elapsed > 2.0:
            self.logger.info(f"Index built successfully in {elapsed:.1f}s")

        return self

    def load_index(self, index_name: str) -> "VectorStore":
        """
        Load an index from disk.

        Args:
            index_name: Name of the index to load.

        Returns:
            Self for method chaining.

        Raises:
            FileNotFoundError: If index doesn't exist.
        """
        faiss_path, metadata_path = self.cache_manager.get_index_path(index_name)

        if not faiss_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(
                f"Index '{index_name}' not found at {faiss_path.parent}"
            )

        # Load FAISS index
        self.index = faiss.read_index(str(faiss_path))  # type: ignore[possibly-missing-attribute]

        # Load metadata and texts
        with open(metadata_path, "rb") as f:
            data = pickle.load(f)
            if isinstance(data, dict):
                # New format with texts
                self.metadata = data.get("metadata", [])
                self.texts = data.get("texts", [])
            else:
                # Old format (backward compatibility)
                self.metadata = data
                self.texts = []

        return self

    def save_index(self, index_name: str) -> None:
        """
        Save the current index to disk.

        Args:
            index_name: Name for the index.
        """
        if self.index is None:
            raise ValueError("No index to save")

        faiss_path, metadata_path = self.cache_manager.get_index_path(index_name)

        # Save FAISS index
        faiss.write_index(self.index, str(faiss_path))  # type: ignore[possibly-missing-attribute]

        # Save metadata and texts
        with open(metadata_path, "wb") as f:
            pickle.dump({"metadata": self.metadata, "texts": self.texts}, f)

    def search(
        self, query_embedding: List[float], k: int = 5
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """
        Search for similar chunks.

        Args:
            query_embedding: Query embedding vector.
            k: Number of results to return.

        Returns:
            List of tuples containing (text, metadata, distance) for each result.
        """
        if self.index is None:
            raise ValueError("Index not loaded or built")

        query_array = np.array([query_embedding], dtype=np.float32)
        distances, indices = self.index.search(query_array, k)  # type: ignore[missing-argument]

        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata):
                text = self.texts[idx] if idx < len(self.texts) else ""
                results.append(
                    (text, self.metadata[idx], float(distances[0][i]))
                )

        return results

    def is_valid(self) -> bool:
        """Check if the index is valid and ready to use."""
        return (
            self.index is not None
            and len(self.metadata) > 0
            and self.index.ntotal == len(self.metadata)
        )
