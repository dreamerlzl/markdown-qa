"""Centralized cache directory management for markdown Q&A system."""

from pathlib import Path
from typing import Optional


class CacheManager:
    """Manages centralized cache directory for indexes and embeddings."""

    DEFAULT_CACHE_DIR = Path.home() / ".markdown-qa" / "cache"

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize cache manager.

        Args:
            cache_dir: Custom cache directory. If None, uses default.
        """
        self.cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Subdirectories
        self.index_dir = self.cache_dir / "indexes"
        self.embedding_dir = self.cache_dir / "embeddings"
        self.index_dir.mkdir(exist_ok=True)
        self.embedding_dir.mkdir(exist_ok=True)

    def get_index_path(self, index_name: str) -> tuple[Path, Path]:
        """
        Get paths for an index (FAISS and metadata files).

        Args:
            index_name: Name of the index.

        Returns:
            Tuple of (faiss_path, metadata_path).
        """
        faiss_path = self.index_dir / f"{index_name}.faiss"
        metadata_path = self.index_dir / f"{index_name}.pkl"
        return faiss_path, metadata_path

    def index_exists(self, index_name: str) -> bool:
        """
        Check if an index exists.

        Args:
            index_name: Name of the index.

        Returns:
            True if both FAISS and metadata files exist.
        """
        faiss_path, metadata_path = self.get_index_path(index_name)
        return faiss_path.exists() and metadata_path.exists()

    def get_manifest_path(self) -> Path:
        """Get path to the manifest file."""
        return self.cache_dir / "indexes.json"
