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
