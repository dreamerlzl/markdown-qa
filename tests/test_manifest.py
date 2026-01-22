"""Tests for manifest file system."""

import json
import tempfile
from pathlib import Path

import pytest

from markdown_qa.manifest import Manifest


class TestManifest:
    """Test manifest file system for tracking directory-to-index mappings."""

    def test_create_manifest(self):
        """Test creating a new manifest file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            assert manifest_path.exists()
            data = json.loads(manifest_path.read_text())
            assert data == {"indexes": {}}

    def test_add_index_mapping(self):
        """Test adding a directory-to-index mapping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs1", "/path/to/docs2"])
            data = json.loads(manifest_path.read_text())
            assert "default" in data["indexes"]
            assert data["indexes"]["default"]["directories"] == [
                "/path/to/docs1",
                "/path/to/docs2",
            ]

    def test_update_index_mapping(self):
        """Test updating an existing index mapping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs1"])
            manifest.update_index("default", ["/path/to/docs1", "/path/to/docs2"])
            data = json.loads(manifest_path.read_text())
            assert data["indexes"]["default"]["directories"] == [
                "/path/to/docs1",
                "/path/to/docs2",
            ]

    def test_read_manifest(self):
        """Test reading an existing manifest file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "indexes": {
                            "default": {
                                "directories": ["/path/to/docs1"],
                                "checksum": "abc123",
                            }
                        }
                    }
                )
            )
            manifest = Manifest(manifest_path)
            data = manifest.read()
            assert "default" in data["indexes"]
            assert data["indexes"]["default"]["directories"] == ["/path/to/docs1"]

    def test_get_index_directories(self):
        """Test getting directories for a specific index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs1", "/path/to/docs2"])
            directories = manifest.get_index_directories("default")
            assert directories == ["/path/to/docs1", "/path/to/docs2"]

    def test_get_index_directories_not_found(self):
        """Test getting directories for non-existent index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            directories = manifest.get_index_directories("nonexistent")
            assert directories is None

    def test_update_checksum(self):
        """Test updating checksum for an index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs1"])
            manifest.update_checksum("default", "new-checksum-123")
            data = json.loads(manifest_path.read_text())
            assert data["indexes"]["default"]["checksum"] == "new-checksum-123"

    def test_list_indexes(self):
        """Test listing all indexes in manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs1"])
            manifest.add_index("project-a", ["/path/to/project-a"])
            indexes = manifest.list_indexes()
            assert "default" in indexes
            assert "project-a" in indexes
