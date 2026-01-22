"""Index cache validation module."""

from pathlib import Path
from typing import Optional, Tuple

from markdown_qa.cache import CacheManager
from markdown_qa.vector_store import VectorStore


class IndexValidator:
    """Validates index cache existence and integrity."""

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        """
        Initialize index validator.

        Args:
            cache_manager: Cache manager instance. If None, creates default.
        """
        self.cache_manager = cache_manager or CacheManager()

    def validate_index(self, index_name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that an index exists and is valid.

        Args:
            index_name: Name of the index to validate.

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        faiss_path, metadata_path = self.cache_manager.get_index_path(index_name)

        # Check if files exist
        if not faiss_path.exists():
            return False, f"FAISS index file not found: {faiss_path}"

        if not metadata_path.exists():
            return False, f"Metadata file not found: {metadata_path}"

        # Try to load the index to validate integrity
        try:
            vector_store = VectorStore(cache_manager=self.cache_manager)
            vector_store.load_index(index_name)

            if not vector_store.is_valid():
                return False, "Index loaded but is invalid (empty or corrupted)"

            return True, None
        except Exception as e:
            return False, f"Failed to load index: {e}"

    def index_exists(self, index_name: str) -> bool:
        """
        Check if an index exists (without full validation).

        Args:
            index_name: Name of the index.

        Returns:
            True if index files exist.
        """
        return self.cache_manager.index_exists(index_name)
