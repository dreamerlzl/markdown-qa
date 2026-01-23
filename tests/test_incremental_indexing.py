"""Tests for incremental indexing functionality."""

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from markdown_qa.manifest import Manifest


# Mock external dependencies that may not be available in test environment
# before they are imported by the modules we test
_mock_modules = {}


def _setup_mocks():
    """Set up mock modules for testing."""
    global _mock_modules
    
    # Create mocks for modules that may not be installed
    if "langchain_text_splitters" not in sys.modules:
        mock_splitters = MagicMock()
        mock_splitters.MarkdownTextSplitter = MagicMock()
        _mock_modules["langchain_text_splitters"] = mock_splitters
        sys.modules["langchain_text_splitters"] = mock_splitters
    
    if "langchain_openai" not in sys.modules:
        mock_openai = MagicMock()
        mock_openai.OpenAIEmbeddings = MagicMock()
        _mock_modules["langchain_openai"] = mock_openai
        sys.modules["langchain_openai"] = mock_openai


def _cleanup_mocks():
    """Clean up mock modules."""
    global _mock_modules
    for mod_name in _mock_modules:
        if mod_name in sys.modules:
            del sys.modules[mod_name]
    _mock_modules = {}


class TestFileChangeDetection:
    """Test file change detection (added/modified/deleted scenarios)."""

    def test_detect_added_file(self):
        """Test detection of newly added markdown file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "cache" / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            
            # Create initial file and store its metadata
            file1 = docs_dir / "existing.md"
            file1.write_text("# Existing")
            
            # Store per-file metadata for the initial state
            manifest.add_index("default", [str(docs_dir)])
            manifest.set_file_metadata("default", str(file1), {
                "mtime": file1.stat().st_mtime,
                "chunk_ids": [1001, 1002]
            })
            
            # Add a new file
            file2 = docs_dir / "new_file.md"
            file2.write_text("# New File")
            
            # Detect changes
            added, modified, deleted = manifest.detect_file_changes(
                "default", [str(docs_dir)]
            )
            
            assert str(file2) in added
            assert str(file1) not in added
            assert len(modified) == 0
            assert len(deleted) == 0

    def test_detect_modified_file(self):
        """Test detection of modified markdown file (mtime changed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "cache" / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            
            # Create file and store its metadata
            file1 = docs_dir / "doc.md"
            file1.write_text("# Original")
            original_mtime = file1.stat().st_mtime
            
            manifest.add_index("default", [str(docs_dir)])
            manifest.set_file_metadata("default", str(file1), {
                "mtime": original_mtime,
                "chunk_ids": [1001, 1002]
            })
            
            # Wait and modify the file
            time.sleep(0.1)
            file1.write_text("# Modified Content")
            
            # Detect changes
            added, modified, deleted = manifest.detect_file_changes(
                "default", [str(docs_dir)]
            )
            
            assert len(added) == 0
            assert str(file1) in modified
            assert len(deleted) == 0

    def test_detect_deleted_file(self):
        """Test detection of deleted markdown file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "cache" / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            
            # Create file and store its metadata
            file1 = docs_dir / "to_delete.md"
            file1.write_text("# Will be deleted")
            
            manifest.add_index("default", [str(docs_dir)])
            manifest.set_file_metadata("default", str(file1), {
                "mtime": file1.stat().st_mtime,
                "chunk_ids": [1001, 1002]
            })
            
            # Delete the file
            file1.unlink()
            
            # Detect changes
            added, modified, deleted = manifest.detect_file_changes(
                "default", [str(docs_dir)]
            )
            
            assert len(added) == 0
            assert len(modified) == 0
            assert str(file1) in deleted

    def test_detect_multiple_changes(self):
        """Test detection of multiple simultaneous changes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "cache" / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            
            # Create initial files
            file_keep = docs_dir / "keep.md"
            file_modify = docs_dir / "modify.md"
            file_delete = docs_dir / "delete.md"
            
            file_keep.write_text("# Keep")
            file_modify.write_text("# Modify")
            file_delete.write_text("# Delete")
            
            manifest.add_index("default", [str(docs_dir)])
            for f in [file_keep, file_modify, file_delete]:
                manifest.set_file_metadata("default", str(f), {
                    "mtime": f.stat().st_mtime,
                    "chunk_ids": [1001]
                })
            
            # Make changes
            time.sleep(0.1)
            file_modify.write_text("# Modified")
            file_delete.unlink()
            file_new = docs_dir / "new.md"
            file_new.write_text("# New")
            
            # Detect changes
            added, modified, deleted = manifest.detect_file_changes(
                "default", [str(docs_dir)]
            )
            
            assert str(file_new) in added
            assert str(file_modify) in modified
            assert str(file_delete) in deleted
            assert str(file_keep) not in added
            assert str(file_keep) not in modified
            assert str(file_keep) not in deleted

    def test_detect_no_changes(self):
        """Test that no changes are detected when nothing changed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "cache" / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            
            file1 = docs_dir / "stable.md"
            file1.write_text("# Stable")
            
            manifest.add_index("default", [str(docs_dir)])
            manifest.set_file_metadata("default", str(file1), {
                "mtime": file1.stat().st_mtime,
                "chunk_ids": [1001]
            })
            
            # Detect changes without modifying anything
            added, modified, deleted = manifest.detect_file_changes(
                "default", [str(docs_dir)]
            )
            
            assert len(added) == 0
            assert len(modified) == 0
            assert len(deleted) == 0


class TestManifestPerFileMetadata:
    """Test manifest per-file metadata storage."""

    def test_set_file_metadata(self):
        """Test storing per-file metadata in manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs"])
            
            manifest.set_file_metadata("default", "/path/to/docs/file.md", {
                "mtime": 1234567890.123,
                "chunk_ids": [1001, 1002, 1003]
            })
            
            data = json.loads(manifest_path.read_text())
            assert "files" in data["indexes"]["default"]
            assert "/path/to/docs/file.md" in data["indexes"]["default"]["files"]
            file_meta = data["indexes"]["default"]["files"]["/path/to/docs/file.md"]
            assert file_meta["mtime"] == 1234567890.123
            assert file_meta["chunk_ids"] == [1001, 1002, 1003]

    def test_get_file_metadata(self):
        """Test retrieving per-file metadata from manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs"])
            manifest.set_file_metadata("default", "/path/to/docs/file.md", {
                "mtime": 1234567890.123,
                "chunk_ids": [1001, 1002]
            })
            
            metadata = manifest.get_file_metadata("default", "/path/to/docs/file.md")
            
            assert metadata is not None
            assert metadata["mtime"] == 1234567890.123
            assert metadata["chunk_ids"] == [1001, 1002]

    def test_get_file_metadata_not_found(self):
        """Test getting metadata for non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs"])
            
            metadata = manifest.get_file_metadata("default", "/nonexistent/file.md")
            
            assert metadata is None

    def test_remove_file_metadata(self):
        """Test removing per-file metadata from manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs"])
            manifest.set_file_metadata("default", "/path/to/docs/file.md", {
                "mtime": 1234567890.123,
                "chunk_ids": [1001, 1002]
            })
            
            manifest.remove_file_metadata("default", "/path/to/docs/file.md")
            
            metadata = manifest.get_file_metadata("default", "/path/to/docs/file.md")
            assert metadata is None

    def test_get_all_file_metadata(self):
        """Test getting all per-file metadata for an index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs"])
            manifest.set_file_metadata("default", "/path/to/docs/file1.md", {
                "mtime": 1234567890.0,
                "chunk_ids": [1001]
            })
            manifest.set_file_metadata("default", "/path/to/docs/file2.md", {
                "mtime": 1234567891.0,
                "chunk_ids": [2001, 2002]
            })
            
            all_files = manifest.get_all_file_metadata("default")
            
            assert len(all_files) == 2
            assert "/path/to/docs/file1.md" in all_files
            assert "/path/to/docs/file2.md" in all_files

    def test_get_chunk_ids_for_file(self):
        """Test getting chunk IDs for a specific file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "indexes.json"
            manifest = Manifest(manifest_path)
            manifest.create()
            manifest.add_index("default", ["/path/to/docs"])
            manifest.set_file_metadata("default", "/path/to/docs/file.md", {
                "mtime": 1234567890.123,
                "chunk_ids": [1001, 1002, 1003]
            })
            
            chunk_ids = manifest.get_chunk_ids_for_file("default", "/path/to/docs/file.md")
            
            assert chunk_ids == [1001, 1002, 1003]


class TestIncrementalUpdateIntegration:
    """Integration tests for incremental index updates."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mock modules before tests."""
        _setup_mocks()
        yield
        _cleanup_mocks()

    def test_incremental_update_add_file(self):
        """Test incremental update when a file is added."""
        # This test will verify the full flow:
        # 1. Build initial index with one file
        # 2. Add a new file
        # 3. Run incremental update
        # 4. Verify only new file was processed
        with tempfile.TemporaryDirectory() as tmpdir:
            from markdown_qa.cache import CacheManager
            from markdown_qa.config import APIConfig
            from markdown_qa.index_manager import IndexManager
            
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()
            
            # Create initial file
            file1 = docs_dir / "initial.md"
            file1.write_text("# Initial Document\n\nSome content here.")
            
            # Mock API config
            api_config = MagicMock(spec=APIConfig)
            api_config.base_url = "https://api.example.com"
            api_config.api_key = "test-key"
            api_config.embedding_model = "text-embedding-3-small"
            
            # Use a custom cache manager with temp directory
            cache_manager = CacheManager(cache_dir=cache_dir)
            manager = IndexManager(cache_manager=cache_manager, api_config=api_config)
            
            # Mock embedding generation to track calls
            embedding_calls = []
            
            with patch("markdown_qa.index_manager.VectorStore") as mock_vs:
                mock_instance = MagicMock()
                mock_instance.build_index.return_value = mock_instance
                mock_instance.is_valid.return_value = True
                # Add metadata and chunk_ids attributes for _store_per_file_metadata
                mock_instance.metadata = [{"source": str(file1)}]
                mock_instance.chunk_ids = [1001]
                mock_vs.return_value = mock_instance
                
                # Build initial index
                manager.load_index("default", [str(docs_dir)])
                
                # Create fake FAISS files so index_exists returns True
                faiss_path, metadata_path = cache_manager.get_index_path("default")
                faiss_path.write_bytes(b"fake faiss data")
                metadata_path.write_bytes(b"fake metadata")
                
                # Add new file
                file2 = docs_dir / "new.md"
                file2.write_text("# New Document\n\nNew content.")
                
                # Run incremental update
                result = manager.incremental_update("default", [str(docs_dir)])
                
                # Verify incremental update was performed
                assert result.added_files == [str(file2)]
                assert result.modified_files == []
                assert result.deleted_files == []

    def test_incremental_update_modify_file(self):
        """Test incremental update when a file is modified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from markdown_qa.cache import CacheManager
            from markdown_qa.config import APIConfig
            from markdown_qa.index_manager import IndexManager
            
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()
            
            file1 = docs_dir / "doc.md"
            file1.write_text("# Original Content")
            
            api_config = MagicMock(spec=APIConfig)
            api_config.base_url = "https://api.example.com"
            api_config.api_key = "test-key"
            api_config.embedding_model = "text-embedding-3-small"
            
            cache_manager = CacheManager(cache_dir=cache_dir)
            manager = IndexManager(cache_manager=cache_manager, api_config=api_config)
            
            with patch("markdown_qa.index_manager.VectorStore") as mock_vs:
                mock_instance = MagicMock()
                mock_instance.build_index.return_value = mock_instance
                mock_instance.is_valid.return_value = True
                # Add metadata and chunk_ids attributes for _store_per_file_metadata
                mock_instance.metadata = [{"source": str(file1)}]
                mock_instance.chunk_ids = [1001]
                mock_vs.return_value = mock_instance
                
                manager.load_index("default", [str(docs_dir)])
                
                # Create fake FAISS files so index_exists returns True
                faiss_path, metadata_path = cache_manager.get_index_path("default")
                faiss_path.write_bytes(b"fake faiss data")
                metadata_path.write_bytes(b"fake metadata")
                
                # Modify file
                time.sleep(0.1)
                file1.write_text("# Modified Content")
                
                result = manager.incremental_update("default", [str(docs_dir)])
                
                assert result.added_files == []
                assert result.modified_files == [str(file1)]
                assert result.deleted_files == []

    def test_incremental_update_delete_file(self):
        """Test incremental update when a file is deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from markdown_qa.cache import CacheManager
            from markdown_qa.config import APIConfig
            from markdown_qa.index_manager import IndexManager
            
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()
            
            file1 = docs_dir / "keep.md"
            file2 = docs_dir / "delete.md"
            file1.write_text("# Keep")
            file2.write_text("# Delete")
            
            api_config = MagicMock(spec=APIConfig)
            api_config.base_url = "https://api.example.com"
            api_config.api_key = "test-key"
            api_config.embedding_model = "text-embedding-3-small"
            
            cache_manager = CacheManager(cache_dir=cache_dir)
            manager = IndexManager(cache_manager=cache_manager, api_config=api_config)
            
            with patch("markdown_qa.index_manager.VectorStore") as mock_vs:
                mock_instance = MagicMock()
                mock_instance.build_index.return_value = mock_instance
                mock_instance.is_valid.return_value = True
                # Add metadata and chunk_ids attributes for both files
                mock_instance.metadata = [{"source": str(file1)}, {"source": str(file2)}]
                mock_instance.chunk_ids = [1001, 1002]
                mock_vs.return_value = mock_instance
                
                manager.load_index("default", [str(docs_dir)])
                
                # Create fake FAISS files so index_exists returns True
                faiss_path, metadata_path = cache_manager.get_index_path("default")
                faiss_path.write_bytes(b"fake faiss data")
                metadata_path.write_bytes(b"fake metadata")
                
                # Delete file
                file2.unlink()
                
                result = manager.incremental_update("default", [str(docs_dir)])
                
                assert result.added_files == []
                assert result.modified_files == []
                assert result.deleted_files == [str(file2)]


class TestFallbackToFullRebuild:
    """Test fallback to full rebuild when incremental update is not possible."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mock modules before tests."""
        _setup_mocks()
        yield
        _cleanup_mocks()

    def test_fallback_when_no_per_file_metadata(self):
        """Test that full rebuild is triggered when manifest lacks per-file data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from markdown_qa.cache import CacheManager
            from markdown_qa.config import APIConfig
            from markdown_qa.index_manager import IndexManager
            
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            
            file1 = docs_dir / "doc.md"
            file1.write_text("# Document")
            
            # Create index files so index_exists returns True
            cache_manager = CacheManager(cache_dir=cache_dir)
            faiss_path, metadata_path = cache_manager.get_index_path("default")
            faiss_path.write_bytes(b"fake faiss data")
            metadata_path.write_bytes(b"fake metadata")
            
            # Create manifest without per-file metadata (old format)
            manifest_path = cache_dir / "indexes.json"
            manifest_path.write_text(json.dumps({
                "indexes": {
                    "default": {
                        "directories": [str(docs_dir)],
                        "checksum": "old-checksum"
                        # No "files" key - old format
                    }
                }
            }))
            
            api_config = MagicMock(spec=APIConfig)
            api_config.base_url = "https://api.example.com"
            api_config.api_key = "test-key"
            api_config.embedding_model = "text-embedding-3-small"
            
            manager = IndexManager(cache_manager=cache_manager, api_config=api_config)
            
            with patch("markdown_qa.index_manager.VectorStore") as mock_vs:
                mock_instance = MagicMock()
                mock_instance.build_index.return_value = mock_instance
                mock_instance.is_valid.return_value = True
                # Add metadata and chunk_ids for the rebuild
                mock_instance.metadata = [{"source": str(file1)}]
                mock_instance.chunk_ids = [1001]
                mock_vs.return_value = mock_instance
                
                # Attempt incremental update - should fall back to full rebuild
                result = manager.incremental_update("default", [str(docs_dir)])
                
                assert result.fallback_to_full_rebuild is True
                assert result.reason == "missing_per_file_metadata"

    def test_fallback_when_index_not_found(self):
        """Test that full rebuild is triggered for non-existent index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from markdown_qa.cache import CacheManager
            from markdown_qa.config import APIConfig
            from markdown_qa.index_manager import IndexManager
            
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()
            
            file1 = docs_dir / "doc.md"
            file1.write_text("# Document")
            
            api_config = MagicMock(spec=APIConfig)
            api_config.base_url = "https://api.example.com"
            api_config.api_key = "test-key"
            api_config.embedding_model = "text-embedding-3-small"
            
            cache_manager = CacheManager(cache_dir=cache_dir)
            manager = IndexManager(cache_manager=cache_manager, api_config=api_config)
            
            with patch("markdown_qa.index_manager.VectorStore") as mock_vs:
                mock_instance = MagicMock()
                mock_instance.build_index.return_value = mock_instance
                mock_instance.is_valid.return_value = True
                mock_vs.return_value = mock_instance
                
                # Attempt incremental update on non-existent index
                result = manager.incremental_update("nonexistent", [str(docs_dir)])
                
                assert result.fallback_to_full_rebuild is True
                assert result.reason == "index_not_found"
