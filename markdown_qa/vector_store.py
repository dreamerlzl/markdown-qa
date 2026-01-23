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
from markdown_qa.loader import generate_chunk_id, load_markdown_files
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
        self.chunk_ids: List[int] = []  # Track chunk IDs for incremental updates
        self._id_to_idx: Dict[int, int] = {}  # Map chunk_id -> index in metadata/texts
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

        # Generate chunk IDs based on file path and chunk index
        # Group chunks by file to assign sequential IDs per file
        file_chunk_counts: Dict[str, int] = {}
        chunk_ids: List[int] = []
        for chunk in chunks:
            file_path = str(chunk["metadata"].get("source", ""))
            chunk_idx = file_chunk_counts.get(file_path, 0)
            chunk_id = generate_chunk_id(file_path, chunk_idx)
            chunk_ids.append(chunk_id)
            file_chunk_counts[file_path] = chunk_idx + 1

        # Generate embeddings
        if show_progress:
            self.logger.info(f"Generating embeddings for {len(chunks)} chunk(s)...")
        texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedding_generator.generate_embeddings(
            texts, show_progress=show_progress
        )

        # Convert to numpy arrays
        embedding_dim = len(embeddings[0])
        embeddings_array = np.array(embeddings, dtype=np.float32)
        ids_array = np.array(chunk_ids, dtype=np.int64)

        # Create FAISS index with ID mapping for incremental updates
        base_index = faiss.IndexFlatL2(embedding_dim)  # type: ignore[possibly-missing-attribute]
        self.index = faiss.IndexIDMap2(base_index)  # type: ignore[possibly-missing-attribute]
        self.index.add_with_ids(embeddings_array, ids_array)  # type: ignore[possibly-missing-attribute]

        # Store metadata, texts, and chunk IDs
        self.metadata = [chunk["metadata"] for chunk in chunks]
        self.texts = [chunk["text"] for chunk in chunks]
        self.chunk_ids = chunk_ids
        self._rebuild_id_map()

        # Save to disk
        self.save_index(index_name)

        elapsed = time.time() - start_time
        if show_progress and elapsed > 2.0:
            self.logger.info(f"Index built successfully in {elapsed:.1f}s")

        return self

    def _rebuild_id_map(self) -> None:
        """Rebuild the chunk_id -> index mapping."""
        self._id_to_idx = {cid: idx for idx, cid in enumerate(self.chunk_ids)}

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

        # Load metadata, texts, and chunk_ids
        with open(metadata_path, "rb") as f:
            data = pickle.load(f)
            if isinstance(data, dict):
                # New format with texts and chunk_ids
                self.metadata = data.get("metadata", [])
                self.texts = data.get("texts", [])
                self.chunk_ids = data.get("chunk_ids", [])
            else:
                # Old format (backward compatibility)
                self.metadata = data
                self.texts = []
                self.chunk_ids = []

        self._rebuild_id_map()
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

        # Save metadata, texts, and chunk_ids
        with open(metadata_path, "wb") as f:
            pickle.dump({
                "metadata": self.metadata,
                "texts": self.texts,
                "chunk_ids": self.chunk_ids,
            }, f)

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
        distances, ids = self.index.search(query_array, k)  # type: ignore[missing-argument]

        results = []
        for i, chunk_id in enumerate(ids[0]):
            if chunk_id == -1:
                # No result found
                continue

            # For IndexIDMap2, search returns chunk IDs, not indices
            # Look up the index in our metadata arrays
            if chunk_id in self._id_to_idx:
                idx = self._id_to_idx[chunk_id]
                text = self.texts[idx] if idx < len(self.texts) else ""
                results.append(
                    (text, self.metadata[idx], float(distances[0][i]))
                )
            elif chunk_id < len(self.metadata):
                # Fallback for old indexes without ID mapping
                text = self.texts[chunk_id] if chunk_id < len(self.texts) else ""
                results.append(
                    (text, self.metadata[chunk_id], float(distances[0][i]))
                )

        return results

    def is_valid(self) -> bool:
        """Check if the index is valid and ready to use."""
        return (
            self.index is not None
            and len(self.metadata) > 0
            and self.index.ntotal == len(self.metadata)
        )

    def remove_chunks(self, chunk_ids_to_remove: List[int]) -> int:
        """
        Remove chunks from the index by their IDs.

        Args:
            chunk_ids_to_remove: List of chunk IDs to remove.

        Returns:
            Number of chunks actually removed.
        """
        if self.index is None:
            raise ValueError("No index loaded")

        if not chunk_ids_to_remove:
            return 0

        # Remove from FAISS index
        ids_array = np.array(chunk_ids_to_remove, dtype=np.int64)
        removed_count = self.index.remove_ids(ids_array)  # type: ignore[possibly-missing-attribute]

        # Remove from metadata, texts, and chunk_ids
        ids_to_remove_set = set(chunk_ids_to_remove)
        new_metadata = []
        new_texts = []
        new_chunk_ids = []

        for idx, chunk_id in enumerate(self.chunk_ids):
            if chunk_id not in ids_to_remove_set:
                new_metadata.append(self.metadata[idx])
                new_texts.append(self.texts[idx] if idx < len(self.texts) else "")
                new_chunk_ids.append(chunk_id)

        self.metadata = new_metadata
        self.texts = new_texts
        self.chunk_ids = new_chunk_ids
        self._rebuild_id_map()

        return removed_count

    def add_chunks_with_ids(
        self,
        chunks: List[Dict[str, Any]],
        chunk_ids: List[int],
        show_progress: bool = False,
    ) -> None:
        """
        Add new chunks to the index with explicit IDs.

        Args:
            chunks: List of chunk dictionaries with 'text' and 'metadata'.
            chunk_ids: List of chunk IDs corresponding to each chunk.
            show_progress: Whether to show progress indicators.
        """
        if self.index is None:
            raise ValueError("No index loaded")

        if not chunks:
            return

        if len(chunks) != len(chunk_ids):
            raise ValueError("chunks and chunk_ids must have the same length")

        # Generate embeddings for new chunks
        texts = [chunk["text"] for chunk in chunks]
        if show_progress:
            self.logger.info(f"Generating embeddings for {len(chunks)} new chunk(s)...")
        embeddings = self.embedding_generator.generate_embeddings(
            texts, show_progress=show_progress
        )

        # Add to FAISS index
        embeddings_array = np.array(embeddings, dtype=np.float32)
        ids_array = np.array(chunk_ids, dtype=np.int64)
        self.index.add_with_ids(embeddings_array, ids_array)  # type: ignore[possibly-missing-attribute]

        # Add to metadata, texts, and chunk_ids
        for i, chunk in enumerate(chunks):
            self.metadata.append(chunk["metadata"])
            self.texts.append(chunk["text"])
            self.chunk_ids.append(chunk_ids[i])

        self._rebuild_id_map()

    def get_chunk_ids_for_file(self, file_path: str) -> List[int]:
        """
        Get all chunk IDs that belong to a specific file.

        Args:
            file_path: Path to the source file.

        Returns:
            List of chunk IDs for the file.
        """
        result = []
        for idx, meta in enumerate(self.metadata):
            # Chunker stores file path as "file_path" in metadata
            source = str(meta.get("file_path", "") or meta.get("source", ""))
            if source == file_path:
                if idx < len(self.chunk_ids):
                    result.append(self.chunk_ids[idx])
        return result

    def get_embedding_dim(self) -> int:
        """Get the embedding dimension of the index."""
        if self.index is None:
            raise ValueError("No index loaded")
        if hasattr(self.index, "d"):
            return self.index.d  # type: ignore[possibly-missing-attribute]
        return 0

    def clone(self) -> "VectorStore":
        """
        Create a deep copy of this VectorStore.

        Returns:
            A new VectorStore with copied data.
        """
        import copy

        new_store = VectorStore(
            cache_manager=self.cache_manager,
            embedding_generator=self.embedding_generator,
            chunker=self.chunker,
        )

        if self.index is not None:
            dim = self.get_embedding_dim()
            base_index = faiss.IndexFlatL2(dim)  # type: ignore[possibly-missing-attribute]
            new_store.index = faiss.IndexIDMap2(base_index)  # type: ignore[possibly-missing-attribute]

            if self.chunk_ids:
                embeddings = []
                for chunk_id in self.chunk_ids:
                    embedding = np.zeros(dim, dtype=np.float32)
                    self.index.reconstruct(chunk_id, embedding)  # type: ignore[possibly-missing-attribute]
                    embeddings.append(embedding)

                if embeddings:
                    embeddings_array = np.array(embeddings, dtype=np.float32)
                    ids_array = np.array(self.chunk_ids, dtype=np.int64)
                    new_store.index.add_with_ids(embeddings_array, ids_array)  # type: ignore[possibly-missing-attribute]

        new_store.metadata = copy.deepcopy(self.metadata)
        new_store.texts = copy.copy(self.texts)
        new_store.chunk_ids = copy.copy(self.chunk_ids)
        new_store._rebuild_id_map()

        return new_store
