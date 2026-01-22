"""Tests for in-memory index manager."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from markdown_qa.cache import CacheManager
from markdown_qa.config import APIConfig
from markdown_qa.index_manager import IndexManager
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
        import time
        
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
