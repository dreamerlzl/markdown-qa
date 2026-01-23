"""Manifest file system for tracking directory-to-index mappings."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class Manifest:
    """Manages manifest file tracking directory-to-index mappings."""

    def __init__(self, manifest_path: Path):
        """
        Initialize manifest.

        Args:
            manifest_path: Path to the manifest JSON file.
        """
        self.manifest_path = manifest_path
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def create(self) -> None:
        """Create a new manifest file if it doesn't exist."""
        if not self.manifest_path.exists():
            self.manifest_path.write_text(json.dumps({"indexes": {}}))

    def read(self) -> Dict[str, Any]:
        """Read the manifest file."""
        if not self.manifest_path.exists():
            return {"indexes": {}}
        with open(self.manifest_path) as f:
            data: Dict[str, Any] = json.load(f)
            return data

    def _write(self, data: Dict[str, Any]) -> None:
        """Write data to manifest file."""
        with open(self.manifest_path, "w") as f:
            json.dump(data, f, indent=2)

    def add_index(self, index_name: str, directories: List[str], checksum: Optional[str] = None) -> None:
        """
        Add or update an index mapping.

        Args:
            index_name: Name of the index.
            directories: List of directory paths included in this index.
            checksum: Optional checksum for change detection.
        """
        self.create()
        data = self.read()
        data["indexes"][index_name] = {
            "directories": directories,
            "checksum": checksum,
        }
        self._write(data)

    def update_index(self, index_name: str, directories: List[str]) -> None:
        """Update directories for an existing index."""
        self.create()
        data = self.read()
        if index_name not in data["indexes"]:
            raise ValueError(f"Index '{index_name}' does not exist")
        data["indexes"][index_name]["directories"] = directories
        self._write(data)

    def update_checksum(self, index_name: str, checksum: str) -> None:
        """Update checksum for an index."""
        self.create()
        data = self.read()
        if index_name not in data["indexes"]:
            raise ValueError(f"Index '{index_name}' does not exist")
        data["indexes"][index_name]["checksum"] = checksum
        self._write(data)

    def get_index_directories(self, index_name: str) -> Optional[List[str]]:
        """Get directories for a specific index."""
        data = self.read()
        if index_name not in data["indexes"]:
            return None
        directories = data["indexes"][index_name].get("directories")
        if isinstance(directories, list):
            return directories
        return None

    def get_index_checksum(self, index_name: str) -> Optional[str]:
        """Get checksum for a specific index."""
        data = self.read()
        if index_name not in data["indexes"]:
            return None
        checksum = data["indexes"][index_name].get("checksum")
        if isinstance(checksum, str):
            return checksum
        return None

    def list_indexes(self) -> List[str]:
        """List all index names in the manifest."""
        data = self.read()
        return list(data["indexes"].keys())

    # Per-file metadata methods for incremental indexing

    def set_file_metadata(
        self, index_name: str, file_path: str, metadata: Dict[str, Any]
    ) -> None:
        """
        Store per-file metadata for incremental indexing.

        Args:
            index_name: Name of the index.
            file_path: Absolute path to the file.
            metadata: Dict containing 'mtime' and 'chunk_ids'.
        """
        self.create()
        data = self.read()
        if index_name not in data["indexes"]:
            raise ValueError(f"Index '{index_name}' does not exist")

        if "files" not in data["indexes"][index_name]:
            data["indexes"][index_name]["files"] = {}

        data["indexes"][index_name]["files"][file_path] = metadata
        self._write(data)

    def get_file_metadata(
        self, index_name: str, file_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get per-file metadata.

        Args:
            index_name: Name of the index.
            file_path: Absolute path to the file.

        Returns:
            Dict with 'mtime' and 'chunk_ids', or None if not found.
        """
        data = self.read()
        if index_name not in data["indexes"]:
            return None

        files = data["indexes"][index_name].get("files", {})
        return files.get(file_path)

    def remove_file_metadata(self, index_name: str, file_path: str) -> None:
        """
        Remove per-file metadata.

        Args:
            index_name: Name of the index.
            file_path: Absolute path to the file.
        """
        data = self.read()
        if index_name not in data["indexes"]:
            return

        files = data["indexes"][index_name].get("files", {})
        if file_path in files:
            del files[file_path]
            data["indexes"][index_name]["files"] = files
            self._write(data)

    def get_all_file_metadata(self, index_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Get all per-file metadata for an index.

        Args:
            index_name: Name of the index.

        Returns:
            Dict mapping file paths to their metadata.
        """
        data = self.read()
        if index_name not in data["indexes"]:
            return {}

        return data["indexes"][index_name].get("files", {})

    def get_chunk_ids_for_file(self, index_name: str, file_path: str) -> List[int]:
        """
        Get chunk IDs for a specific file.

        Args:
            index_name: Name of the index.
            file_path: Absolute path to the file.

        Returns:
            List of chunk IDs, or empty list if not found.
        """
        metadata = self.get_file_metadata(index_name, file_path)
        if metadata is None:
            return []
        return metadata.get("chunk_ids", [])

    def has_per_file_metadata(self, index_name: str) -> bool:
        """
        Check if an index has per-file metadata (for incremental updates).

        Args:
            index_name: Name of the index.

        Returns:
            True if per-file metadata exists, False otherwise.
        """
        data = self.read()
        if index_name not in data["indexes"]:
            return False

        files = data["indexes"][index_name].get("files", {})
        return len(files) > 0

    def detect_file_changes(
        self, index_name: str, directories: List[str]
    ) -> tuple[set[str], set[str], set[str]]:
        """
        Detect which files have been added, modified, or deleted.

        Args:
            index_name: Name of the index.
            directories: List of directories to scan.

        Returns:
            Tuple of (added, modified, deleted) file path sets.
        """
        # Get stored file metadata
        stored_files = self.get_all_file_metadata(index_name)
        stored_paths = set(stored_files.keys())

        # Scan current files in directories
        current_files: Dict[str, float] = {}
        for dir_path in directories:
            dir_obj = Path(dir_path)
            if not dir_obj.exists() or not dir_obj.is_dir():
                continue
            for md_file in dir_obj.rglob("*.md"):
                try:
                    current_files[str(md_file)] = md_file.stat().st_mtime
                except OSError:
                    continue

        current_paths = set(current_files.keys())

        # Calculate changes
        added = current_paths - stored_paths
        deleted = stored_paths - current_paths

        # Check for modified files (mtime changed)
        modified = set()
        for file_path in current_paths & stored_paths:
            stored_mtime = stored_files[file_path].get("mtime", 0)
            current_mtime = current_files[file_path]
            if current_mtime != stored_mtime:
                modified.add(file_path)

        return added, modified, deleted
