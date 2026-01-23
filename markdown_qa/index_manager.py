"""In-memory index manager module."""

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from markdown_qa.cache import CacheManager
from markdown_qa.config import APIConfig
from markdown_qa.index_validator import IndexValidator
from markdown_qa.loader import (
    compute_directories_checksum,
    generate_chunk_id,
    get_file_mtimes,
    load_single_file,
)
from markdown_qa.manifest import Manifest
from markdown_qa.vector_store import VectorStore


@dataclass
class IncrementalUpdateResult:
    """Result of an incremental index update."""

    added_files: List[str] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    deleted_files: List[str] = field(default_factory=list)
    fallback_to_full_rebuild: bool = False
    reason: Optional[str] = None

    @property
    def has_changes(self) -> bool:
        """Return True if any files were changed."""
        return bool(self.added_files or self.modified_files or self.deleted_files)


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

                        # Ensure per-file metadata exists (for indexes created before incremental support)
                        if not self.manifest.has_per_file_metadata(index_name):
                            self._store_per_file_metadata(index_name, directories, vector_store)

                        return
                except Exception:
                    # If loading fails, build new index
                    pass

            # Build new index using full rebuild (includes per-file metadata)
            self._do_full_rebuild(index_name, directories)

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

    def incremental_update(
        self, index_name: str, directories: List[str]
    ) -> IncrementalUpdateResult:
        """
        Perform an incremental index update.

        Only processes files that have been added, modified, or deleted since
        the last index build. Falls back to full rebuild if incremental update
        is not possible.

        Args:
            index_name: Name of the index.
            directories: Directories to check for changes.

        Returns:
            IncrementalUpdateResult with details about what was updated.
        """
        # Check if index exists
        if not self.validator.index_exists(index_name):
            self._do_full_rebuild(index_name, directories)
            return IncrementalUpdateResult(
                fallback_to_full_rebuild=True, reason="index_not_found"
            )

        # Check if we have per-file metadata for incremental updates
        if not self.manifest.has_per_file_metadata(index_name):
            self._do_full_rebuild(index_name, directories)
            return IncrementalUpdateResult(
                fallback_to_full_rebuild=True, reason="missing_per_file_metadata"
            )

        # Detect file changes
        added, modified, deleted = self.manifest.detect_file_changes(
            index_name, directories
        )

        result = IncrementalUpdateResult(
            added_files=list(added),
            modified_files=list(modified),
            deleted_files=list(deleted),
        )

        # If no changes, nothing to do
        if not result.has_changes:
            return result

        # Get current index
        current_index = self.get_index()
        if current_index is None:
            self._do_full_rebuild(index_name, directories)
            return IncrementalUpdateResult(
                fallback_to_full_rebuild=True, reason="no_current_index"
            )

        # Perform incremental update
        from markdown_qa.chunker import MarkdownChunker
        chunker = MarkdownChunker()

        # 1. Remove chunks for deleted and modified files
        chunks_to_remove: List[int] = []
        for file_path in result.deleted_files + result.modified_files:
            chunk_ids = self.manifest.get_chunk_ids_for_file(index_name, file_path)
            chunks_to_remove.extend(chunk_ids)
            self.manifest.remove_file_metadata(index_name, file_path)

        if chunks_to_remove:
            current_index.remove_chunks(chunks_to_remove)

        # 2. Add chunks for added and modified files
        new_chunks: List[Dict[str, Any]] = []
        new_chunk_ids: List[int] = []
        file_mtimes = get_file_mtimes(directories)

        for file_path in result.added_files + result.modified_files:
            try:
                path, content = load_single_file(file_path)
                file_chunks = chunker.chunk_files([(path, content)])

                file_chunk_ids: List[int] = []
                for idx, chunk in enumerate(file_chunks):
                    chunk_id = generate_chunk_id(file_path, idx)
                    new_chunks.append(chunk)
                    new_chunk_ids.append(chunk_id)
                    file_chunk_ids.append(chunk_id)

                # Store per-file metadata
                self.manifest.set_file_metadata(index_name, file_path, {
                    "mtime": file_mtimes.get(file_path, 0),
                    "chunk_ids": file_chunk_ids,
                })
            except Exception:
                # Skip files that can't be processed
                continue

        if new_chunks:
            current_index.add_chunks_with_ids(new_chunks, new_chunk_ids)

        # Save the updated index
        current_index.save_index(index_name)

        # Update overall checksum
        checksum = compute_directories_checksum(directories)
        self.update_checksum(index_name, directories, checksum)

        return result

    def _do_full_rebuild(self, index_name: str, directories: List[str]) -> None:
        """Perform a full index rebuild and store per-file metadata."""
        vector_store = VectorStore(
            cache_manager=self.cache_manager,
            api_config=self.api_config,
        )
        vector_store.build_index(directories, index_name=index_name, show_progress=True)
        self.swap_index(vector_store)

        # Update checksum first to ensure index exists in manifest
        checksum = compute_directories_checksum(directories)
        self.update_checksum(index_name, directories, checksum)

        # Store per-file metadata for future incremental updates
        self._store_per_file_metadata(index_name, directories, vector_store)

    def _store_per_file_metadata(
        self, index_name: str, directories: List[str], vector_store: VectorStore
    ) -> None:
        """Store per-file metadata after building an index."""
        file_mtimes = get_file_mtimes(directories)

        # Group chunk IDs by source file
        # Note: Chunker stores file path as "file_path" in metadata
        file_to_chunks: Dict[str, List[int]] = {}
        for idx, meta in enumerate(vector_store.metadata):
            source = str(meta.get("file_path", "") or meta.get("source", ""))
            if source and idx < len(vector_store.chunk_ids):
                if source not in file_to_chunks:
                    file_to_chunks[source] = []
                file_to_chunks[source].append(vector_store.chunk_ids[idx])

        # Store metadata for each file
        for file_path, chunk_ids in file_to_chunks.items():
            self.manifest.set_file_metadata(index_name, file_path, {
                "mtime": file_mtimes.get(file_path, 0),
                "chunk_ids": chunk_ids,
            })
