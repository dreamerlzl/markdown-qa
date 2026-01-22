"""Tests for server configuration module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from markdown_qa.config import APIConfig
from markdown_qa.server_config import ServerConfig


class TestServerConfig:
    """Test server configuration."""

    def test_default_configuration(self):
        """Test default server configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test directories
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            # Mock API config
            api_config = type("MockAPIConfig", (), {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
            })()

            config = ServerConfig(
                directories=[str(doc_dir)],
                api_config=api_config,
            )

            assert config.port == 8765
            assert config.directories == [str(doc_dir)]
            assert config.reload_interval == 300
            assert config.index_name == "default"

    def test_custom_configuration(self):
        """Test custom server configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            api_config = type("MockAPIConfig", (), {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
            })()

            config = ServerConfig(
                port=9000,
                directories=[str(doc_dir)],
                reload_interval=600,
                index_name="custom",
                api_config=api_config,
            )

            assert config.port == 9000
            assert config.reload_interval == 600
            assert config.index_name == "custom"

    def test_directories_from_env(self):
        """Test reading directories from environment variable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_dir1 = Path(tmpdir) / "docs1"
            doc_dir2 = Path(tmpdir) / "docs2"
            doc_dir1.mkdir()
            doc_dir2.mkdir()

            # Use a non-existent config file path to ensure env var is used
            fake_config_dir = Path(tmpdir) / "no_config"
            fake_config_yaml = fake_config_dir / "config.yaml"

            api_config = type("MockAPIConfig", (), {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
            })()

            os.environ["MARKDOWN_QA_DIRECTORIES"] = f"{doc_dir1},{doc_dir2}"

            try:
                with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", fake_config_yaml), \
                     patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_TOML", fake_config_dir / "config.toml"):
                    config = ServerConfig(api_config=api_config)
                    assert len(config.directories) == 2
                    assert str(doc_dir1) in config.directories
                    assert str(doc_dir2) in config.directories
            finally:
                del os.environ["MARKDOWN_QA_DIRECTORIES"]

    def test_validation_missing_directories(self):
        """Test validation fails when no directories provided."""
        api_config = type("MockAPIConfig", (), {
            "base_url": "https://api.example.com",
            "api_key": "test-key",
        })()

        with pytest.raises(ValueError, match="No directories specified"):
            ServerConfig(directories=[], api_config=api_config)

    def test_validation_invalid_directory(self):
        """Test validation fails when directory doesn't exist."""
        api_config = type("MockAPIConfig", (), {
            "base_url": "https://api.example.com",
            "api_key": "test-key",
        })()

        with pytest.raises(ValueError, match="Directory does not exist"):
            ServerConfig(directories=["/nonexistent/path"], api_config=api_config)

    def test_validation_invalid_port(self):
        """Test validation fails for invalid port."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            api_config = type("MockAPIConfig", (), {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
            })()

            with pytest.raises(ValueError, match="Invalid port"):
                ServerConfig(
                    port=0,
                    directories=[str(doc_dir)],
                    api_config=api_config,
                )

            with pytest.raises(ValueError, match="Invalid port"):
                ServerConfig(
                    port=70000,
                    directories=[str(doc_dir)],
                    api_config=api_config,
                )

    def test_validation_invalid_reload_interval(self):
        """Test validation fails for invalid reload interval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            api_config = type("MockAPIConfig", (), {
                "base_url": "https://api.example.com",
                "api_key": "test-key",
            })()

            with pytest.raises(ValueError, match="Invalid reload interval"):
                ServerConfig(
                    reload_interval=0,
                    directories=[str(doc_dir)],
                    api_config=api_config,
                )
