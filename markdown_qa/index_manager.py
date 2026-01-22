"""In-memory index manager module."""

import threading
from typing import Dict, Optional, Tuple

from markdown_qa.cache import CacheManager
from markdown_qa.config import APIConfig
from markdown_qa.index_validator import IndexValidator
from markdown_qa.loader import compute_directories_checksum
from markdown_qa.manifest import Manifest
from markdown_qa.vector_store import VectorStore


class IndexManager:
    """Manages in-memory indexes with atomic swapping support."""

    def __init__(
        self,
        cache_manager: Optional[CacheManager] = None,
        api_config: Optional[APIConfig] = None,
    ):
        """
        Initialize index manager.

        Args:
            cache_manager: Cache manager instance. If None, creates default.
            api_config: API configuration. If None, creates from defaults.
        """
        self.cache_manager = cache_manager or CacheManager()
        self.api_config = api_config or APIConfig()

        # Current index (used for queries)
        self._index: Optional[VectorStore] = None
        self._index_lock = threading.RLock()  # Reentrant lock for thread safety

        # Index validator
        self.validator = IndexValidator(cache_manager=self.cache_manager)

        # Manifest for tracking checksums
        self.manifest = Manifest(self.cache_manager.get_manifest_path())

    def load_index(self, index_name: str, directories: list[str]) -> None:
        """
        Load or build an index.

        Args:
            index_name: Name of the index.
            directories: Directories to index if index doesn't exist.
        """
        with self._index_lock:
            # Try to load from cache first
            if self.validator.index_exists(index_name):
                try:
                    is_valid, error = self.validator.validate_index(index_name)
                    if is_valid:
                        vector_store = VectorStore(
                            cache_manager=self.cache_manager,
                            api_config=self.api_config,
                        )
                        vector_store.load_index(index_name)
                        self._index = vector_store
                        # Ensure checksum is stored (for indexes created before checksum support)
                        if self.manifest.get_index_checksum(index_name) is None:
                            checksum = compute_directories_checksum(directories)
                            self.update_checksum(index_name, directories, checksum)
                        return
                except Exception:
                    # If loading fails, build new index
                    pass

            # Build new index
            vector_store = VectorStore(
                cache_manager=self.cache_manager,
                api_config=self.api_config,
            )
            vector_store.build_index(
                directories, index_name=index_name, show_progress=True
            )
            self._index = vector_store

            # Store the checksum for the newly built index
            checksum = compute_directories_checksum(directories)
            self.update_checksum(index_name, directories, checksum)

    def get_index(self) -> Optional[VectorStore]:
        """
        Get the current index (thread-safe).

        Returns:
            Current vector store index or None if not loaded.
        """
        with self._index_lock:
            return self._index

    def swap_index(self, new_index: VectorStore) -> None:
        """
        Atomically swap to a new index (thread-safe).

        Args:
            new_index: New vector store index to swap to.
        """
        with self._index_lock:
            self._index = new_index

    def rebuild_index(
        self, index_name: str, directories: list[str]
    ) -> VectorStore:
        """
        Rebuild an index in the background (doesn't swap immediately).

        Args:
            index_name: Name of the index.
            directories: Directories to index.

        Returns:
            Newly built vector store index.
        """
        # Build new index (this doesn't affect current index)
        vector_store = VectorStore(
            cache_manager=self.cache_manager,
            api_config=self.api_config,
        )
        vector_store.build_index(
            directories, index_name=index_name, show_progress=True
        )
        return vector_store

    def is_ready(self) -> bool:
        """
        Check if index is ready for queries.

        Returns:
            True if index is loaded and valid.
        """
        with self._index_lock:
            return self._index is not None and self._index.is_valid()

    def has_changes(self, index_name: str, directories: list[str]) -> Tuple[bool, str]:
        """
        Check if directories have changed since last index build.

        Args:
            index_name: Name of the index.
            directories: Directories to check.

        Returns:
            Tuple of (has_changes, current_checksum).
        """
        current_checksum = compute_directories_checksum(directories)
        stored_checksum = self.manifest.get_index_checksum(index_name)

        if stored_checksum is None:
            # No stored checksum, assume changes exist
            return True, current_checksum

        return current_checksum != stored_checksum, current_checksum

    def update_checksum(self, index_name: str, directories: list[str], checksum: str) -> None:
        """
        Update the stored checksum for an index.

        Args:
            index_name: Name of the index.
            directories: Directories included in the index.
            checksum: New checksum to store.
        """
        # Ensure index entry exists in manifest, then update checksum
        try:
            self.manifest.update_checksum(index_name, checksum)
        except ValueError:
            # Index doesn't exist in manifest, add it
            self.manifest.add_index(index_name, directories, checksum)
