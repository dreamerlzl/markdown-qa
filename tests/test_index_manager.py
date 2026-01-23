"""Tests for in-memory index manager."""

import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from markdown_qa.cache import CacheManager
from markdown_qa.config import APIConfig
from markdown_qa.index_manager import IndexManager, IncrementalUpdateResult
from markdown_qa.vector_store import VectorStore


class TestIndexManager:
    """Test in-memory index manager."""

    def test_load_index(self):
        """Test loading an index."""
        api_config = MagicMock()
        api_config.base_url = "https://api.example.com"
        api_config.api_key = "test-key"

        manager = IndexManager(api_config=api_config)
        
        # Mock VectorStore to avoid actual API calls
        mock_vector_store = MagicMock()
        mock_vector_store.is_valid.return_value = True
        
        with patch("markdown_qa.index_manager.VectorStore") as mock_vs_class, \
             patch.object(manager.validator, "index_exists") as mock_exists:
            
            mock_exists.return_value = False  # Index doesn't exist, so it will build
            mock_vs_instance = MagicMock()
            mock_vs_instance.build_index.return_value = mock_vs_instance
            mock_vs_instance.is_valid.return_value = True
            mock_vs_class.return_value = mock_vs_instance
            
            manager.load_index("test", ["/fake/path"])
            
            # Verify VectorStore was created and build_index was called
            mock_vs_class.assert_called_once()
            mock_vs_instance.build_index.assert_called_once()
            assert manager.is_ready() is True

    def test_get_index_thread_safe(self):
        """Test that get_index is thread-safe."""
        api_config = MagicMock(spec=APIConfig)
        manager = IndexManager(api_config=api_config)
        
        # Initially no index
        assert manager.get_index() is None
        
        # Set a mock index
        mock_index = MagicMock()
        manager.swap_index(mock_index)
        
        assert manager.get_index() == mock_index

    def test_swap_index_atomic(self):
        """Test atomic index swapping."""
        api_config = MagicMock(spec=APIConfig)
        manager = IndexManager(api_config=api_config)
        
        mock_index1 = MagicMock()
        mock_index2 = MagicMock()
        
        manager.swap_index(mock_index1)
        assert manager.get_index() == mock_index1
        
        manager.swap_index(mock_index2)
        assert manager.get_index() == mock_index2

    def test_is_ready(self):
        """Test checking if index is ready."""
        api_config = MagicMock(spec=APIConfig)
        manager = IndexManager(api_config=api_config)
        
        assert manager.is_ready() is False
        
        mock_index = MagicMock()
        mock_index.is_valid.return_value = True
        manager.swap_index(mock_index)
        
        assert manager.is_ready() is True

    def test_has_changes_no_stored_checksum(self):
        """Test has_changes returns True when no checksum is stored."""
        api_config = MagicMock(spec=APIConfig)
        manager = IndexManager(api_config=api_config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a markdown file
            md_file = Path(tmpdir) / "test.md"
            md_file.write_text("# Test")
            
            has_changes, checksum = manager.has_changes("test", [tmpdir])
            
            # Should return True because no checksum is stored
            assert has_changes is True
            assert checksum  # Should have a non-empty checksum

    def test_has_changes_same_checksum(self):
        """Test has_changes returns False when checksum matches."""
        api_config = MagicMock(spec=APIConfig)
        manager = IndexManager(api_config=api_config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a markdown file
            md_file = Path(tmpdir) / "test.md"
            md_file.write_text("# Test")
            
            # Get the checksum and store it
            has_changes, checksum = manager.has_changes("test", [tmpdir])
            manager.update_checksum("test", [tmpdir], checksum)
            
            # Now check again - should return False
            has_changes, new_checksum = manager.has_changes("test", [tmpdir])
            
            assert has_changes is False
            assert new_checksum == checksum

    def test_has_changes_file_modified(self):
        """Test has_changes returns True when file is modified."""
        api_config = MagicMock(spec=APIConfig)
        manager = IndexManager(api_config=api_config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a markdown file
            md_file = Path(tmpdir) / "test.md"
            md_file.write_text("# Test")
            
            # Get the checksum and store it
            has_changes, checksum = manager.has_changes("test", [tmpdir])
            manager.update_checksum("test", [tmpdir], checksum)
            
            # Wait a bit and modify the file
            time.sleep(0.1)
            md_file.write_text("# Test Modified")
            
            # Now check again - should return True
            has_changes, new_checksum = manager.has_changes("test", [tmpdir])
            
            assert has_changes is True
            assert new_checksum != checksum


class TestPerFileMetadata:
    """Tests for per-file metadata storage (prevents regression of missing_per_file_metadata bug)."""

    def test_store_per_file_metadata_uses_file_path_field(self):
        """Test that _store_per_file_metadata correctly reads 'file_path' from chunk metadata.
        
        This is a regression test for a bug where the code looked for 'source' field
        but the chunker stores the path as 'file_path', causing per-file metadata
        to never be stored.
        """
        api_config = MagicMock(spec=APIConfig)
        manager = IndexManager(api_config=api_config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            md_file1 = Path(tmpdir) / "test1.md"
            md_file2 = Path(tmpdir) / "test2.md"
            md_file1.write_text("# Test 1\nContent 1")
            md_file2.write_text("# Test 2\nContent 2")
            
            # Create a mock vector store with metadata using 'file_path' field
            # (matching what MarkdownChunker actually produces)
            mock_vector_store = MagicMock(spec=VectorStore)
            mock_vector_store.metadata = [
                {"file_path": str(md_file1), "section": "Test 1"},
                {"file_path": str(md_file1), "section": "Test 1"},
                {"file_path": str(md_file2), "section": "Test 2"},
            ]
            mock_vector_store.chunk_ids = [1001, 1002, 2001]
            
            # Set up the index in the manifest first
            manager.update_checksum("test", [tmpdir], "dummy-checksum")
            
            # Call _store_per_file_metadata
            manager._store_per_file_metadata("test", [tmpdir], mock_vector_store)
            
            # Verify per-file metadata was stored
            assert manager.manifest.has_per_file_metadata("test") is True
            
            # Verify correct chunk IDs are stored for each file
            file1_metadata = manager.manifest.get_file_metadata("test", str(md_file1))
            file2_metadata = manager.manifest.get_file_metadata("test", str(md_file2))
            
            assert file1_metadata is not None
            assert file2_metadata is not None
            assert file1_metadata["chunk_ids"] == [1001, 1002]
            assert file2_metadata["chunk_ids"] == [2001]

    def test_store_per_file_metadata_fallback_to_source_field(self):
        """Test that _store_per_file_metadata also works with legacy 'source' field."""
        api_config = MagicMock(spec=APIConfig)
        manager = IndexManager(api_config=api_config)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            md_file = Path(tmpdir) / "test.md"
            md_file.write_text("# Test")
            
            # Create a mock vector store with metadata using legacy 'source' field
            mock_vector_store = MagicMock(spec=VectorStore)
            mock_vector_store.metadata = [
                {"source": str(md_file), "section": "Test"},
            ]
            mock_vector_store.chunk_ids = [1001]
            
            manager.update_checksum("test", [tmpdir], "dummy-checksum")
            manager._store_per_file_metadata("test", [tmpdir], mock_vector_store)
            
            assert manager.manifest.has_per_file_metadata("test") is True
            file_metadata = manager.manifest.get_file_metadata("test", str(md_file))
            assert file_metadata is not None
            assert file_metadata["chunk_ids"] == [1001]

    def test_incremental_update_after_full_rebuild_no_fallback(self):
        """Test that incremental updates don't fallback after a full rebuild.
        
        This is a regression test: previously, per-file metadata was never stored
        due to field name mismatch, causing every incremental_update() call to
        fallback to full rebuild with reason 'missing_per_file_metadata'.
        """
        api_config = MagicMock(spec=APIConfig)
        
        with tempfile.TemporaryDirectory() as cache_dir, \
             tempfile.TemporaryDirectory() as docs_dir:
            
            cache_manager = CacheManager(Path(cache_dir))
            manager = IndexManager(cache_manager=cache_manager, api_config=api_config)
            
            # Create test files
            md_file = Path(docs_dir) / "test.md"
            md_file.write_text("# Test\nSome content here")
            
            # Create a mock vector store that simulates real chunker output
            mock_vector_store = MagicMock(spec=VectorStore)
            mock_vector_store.metadata = [
                {"file_path": str(md_file), "section": "Test"},
            ]
            mock_vector_store.chunk_ids = [1001]
            mock_vector_store.is_valid.return_value = True
            mock_vector_store.build_index.return_value = mock_vector_store
            
            # Patch VectorStore at the module level since _do_full_rebuild creates it directly
            with patch("markdown_qa.index_manager.VectorStore", return_value=mock_vector_store):
                manager._do_full_rebuild("test", [docs_dir])
            
            # Verify per-file metadata was stored
            assert manager.manifest.has_per_file_metadata("test") is True
            
            # Now call incremental_update - it should NOT fallback
            with patch.object(manager.validator, "index_exists", return_value=True):
                result = manager.incremental_update("test", [docs_dir])
            
            # Should not have fallen back to full rebuild
            assert result.fallback_to_full_rebuild is False
            assert result.reason != "missing_per_file_metadata"

    def test_chunker_metadata_field_name_consistency(self):
        """Test that chunker uses 'file_path' field which index_manager expects.
        
        This documents the expected metadata format contract between chunker
        and index_manager to prevent future field name mismatches.
        """
        from markdown_qa.chunker import MarkdownChunker
        
        chunker = MarkdownChunker()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            md_file = Path(tmpdir) / "test.md"
            md_file.write_text("# Test\nSome content")
            
            chunks = chunker.chunk_file(md_file, "# Test\nSome content")
            
            assert len(chunks) > 0
            # Verify the chunker uses 'file_path' field
            assert "file_path" in chunks[0]["metadata"]
            assert chunks[0]["metadata"]["file_path"] == str(md_file)


class TestVectorStoreMetadataFieldName:
    """Tests for VectorStore metadata field name handling."""

    def test_get_chunk_ids_for_file_uses_file_path_field(self):
        """Test that get_chunk_ids_for_file correctly reads 'file_path' from metadata."""
        mock_cache_manager = MagicMock(spec=CacheManager)
        mock_embedding_gen = MagicMock()
        
        vector_store = VectorStore(
            cache_manager=mock_cache_manager,
            embedding_generator=mock_embedding_gen,
        )
        
        # Set up metadata with 'file_path' field (matching chunker output)
        vector_store.metadata = [
            {"file_path": "/path/to/file1.md", "section": "Test 1"},
            {"file_path": "/path/to/file1.md", "section": "Test 1"},
            {"file_path": "/path/to/file2.md", "section": "Test 2"},
        ]
        vector_store.chunk_ids = [1001, 1002, 2001]
        
        # Should find chunks for file1
        file1_chunks = vector_store.get_chunk_ids_for_file("/path/to/file1.md")
        assert file1_chunks == [1001, 1002]
        
        # Should find chunks for file2
        file2_chunks = vector_store.get_chunk_ids_for_file("/path/to/file2.md")
        assert file2_chunks == [2001]
        
        # Should return empty for non-existent file
        missing_chunks = vector_store.get_chunk_ids_for_file("/path/to/missing.md")
        assert missing_chunks == []

    def test_get_chunk_ids_for_file_fallback_to_source_field(self):
        """Test that get_chunk_ids_for_file also works with legacy 'source' field."""
        mock_cache_manager = MagicMock(spec=CacheManager)
        mock_embedding_gen = MagicMock()
        
        vector_store = VectorStore(
            cache_manager=mock_cache_manager,
            embedding_generator=mock_embedding_gen,
        )
        
        # Set up metadata with legacy 'source' field
        vector_store.metadata = [
            {"source": "/path/to/file.md", "section": "Test"},
        ]
        vector_store.chunk_ids = [1001]
        
        chunks = vector_store.get_chunk_ids_for_file("/path/to/file.md")
        assert chunks == [1001]
