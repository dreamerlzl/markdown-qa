"""Tests for server configuration hot reload."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from markdown_qa.config import APIConfig
from markdown_qa.server_config import ServerConfig


class TestServerConfigReload:
    """Test server configuration reload functionality."""

    def test_get_config_file_path(self):
        """Test getting config file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.yaml"
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            # Create config file first
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, "w") as f:
                yaml.dump({
                    "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                    "server": {"port": 8765, "directories": [str(doc_dir)], "reload_interval": 300}
                }, f)

            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", config_file):
                from markdown_qa.config import APIConfig
                api_config = APIConfig(config_file=config_file)
                config = ServerConfig(config_file=config_file, api_config=api_config)
                assert config.get_config_file_path() == config_file

    def test_reload_directories(self):
        """Test reloading directories from config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.yaml"
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            # Create initial config file
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, "w") as f:
                yaml.dump({
                    "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                    "server": {
                        "port": 8765,
                        "directories": [str(doc_dir)],
                        "reload_interval": 300,
                    }
                }, f)

            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", config_file):
                from markdown_qa.config import APIConfig
                api_config = APIConfig(config_file=config_file)
                config = ServerConfig(config_file=config_file, api_config=api_config)
                original_dirs = config.directories.copy()

                # Update config file
                new_doc_dir = Path(tmpdir) / "new_docs"
                new_doc_dir.mkdir()
                with open(config_file, "w") as f:
                    yaml.dump({
                        "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                        "server": {
                            "port": 8765,
                            "directories": [str(new_doc_dir)],
                            "reload_interval": 300,
                        }
                    }, f)

                result = config.reload(preserve_cli_overrides=False)
                assert "directories" in result["changed"]
                assert str(new_doc_dir) in config.directories
                assert result["requires_restart"] is False

    def test_reload_reload_interval(self):
        """Test reloading reload_interval from config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.yaml"
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", config_file), \
                 patch("markdown_qa.config.APIConfig") as mock_api_config_class:
                # Create mock API config instance
                mock_api_config = MagicMock()
                mock_api_config.base_url = "https://api.example.com/v1"
                mock_api_config.api_key = "test-key"
                mock_api_config_class.return_value = mock_api_config

                # Create initial config
                config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(config_file, "w") as f:
                    yaml.dump({
                        "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                        "server": {
                            "port": 8765,
                            "directories": [str(doc_dir)],
                            "reload_interval": 300,
                        }
                    }, f)

            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", config_file):
                from markdown_qa.config import APIConfig
                api_config = APIConfig(config_file=config_file)
                config = ServerConfig(config_file=config_file, api_config=api_config)
                assert config.reload_interval == 300

                # Update config file
                with open(config_file, "w") as f:
                    yaml.dump({
                        "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                        "server": {
                            "port": 8765,
                            "directories": [str(doc_dir)],
                            "reload_interval": 600,
                        }
                    }, f)

                result = config.reload(preserve_cli_overrides=False)
                assert "reload_interval" in result["changed"]
                assert config.reload_interval == 600
                assert result["requires_restart"] is False

    def test_reload_port_requires_restart(self):
        """Test that port changes require restart."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.yaml"
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", config_file), \
                 patch("markdown_qa.config.APIConfig") as mock_api_config_class:
                # Create mock API config instance
                mock_api_config = MagicMock()
                mock_api_config.base_url = "https://api.example.com/v1"
                mock_api_config.api_key = "test-key"
                mock_api_config_class.return_value = mock_api_config

                # Create initial config
                config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(config_file, "w") as f:
                    yaml.dump({
                        "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                        "server": {
                            "port": 8765,
                            "directories": [str(doc_dir)],
                            "reload_interval": 300,
                        }
                    }, f)

            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", config_file):
                from markdown_qa.config import APIConfig
                api_config = APIConfig(config_file=config_file)
                config = ServerConfig(config_file=config_file, api_config=api_config)
                assert config.port == 8765

                # Update config file with new port
                with open(config_file, "w") as f:
                    yaml.dump({
                        "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                        "server": {
                            "port": 9000,
                            "directories": [str(doc_dir)],
                            "reload_interval": 300,
                        }
                    }, f)

                result = config.reload(preserve_cli_overrides=False)
                assert "port" in result["changed"]
                assert result["requires_restart"] is True

    def test_reload_preserves_cli_overrides(self):
        """Test that CLI overrides are preserved when reloading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.yaml"
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", config_file), \
                 patch("markdown_qa.config.APIConfig") as mock_api_config_class:
                # Create mock API config instance
                mock_api_config = MagicMock()
                mock_api_config.base_url = "https://api.example.com/v1"
                mock_api_config.api_key = "test-key"
                mock_api_config_class.return_value = mock_api_config

                # Create initial config
                config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(config_file, "w") as f:
                    yaml.dump({
                        "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                        "server": {
                            "port": 8765,
                            "directories": [str(doc_dir)],
                            "reload_interval": 300,
                        }
                    }, f)

            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", config_file):
                from markdown_qa.config import APIConfig
                api_config = APIConfig(config_file=config_file)
                # Create config with CLI override
                new_doc_dir = Path(tmpdir) / "cli_docs"
                new_doc_dir.mkdir()
                config = ServerConfig(
                    config_file=config_file,
                    api_config=api_config,
                    directories=[str(new_doc_dir)]
                )

                # Update config file
                with open(config_file, "w") as f:
                    yaml.dump({
                        "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                        "server": {
                            "port": 8765,
                            "directories": [str(doc_dir)],
                            "reload_interval": 600,
                        }
                    }, f)

                result = config.reload(preserve_cli_overrides=True)
                # Directories should not change (CLI override preserved)
                assert str(new_doc_dir) in config.directories
                # But reload_interval should change (no CLI override)
                assert "reload_interval" in result["changed"]

    def test_reload_validation_failure(self):
        """Test that validation failures prevent reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_file = config_dir / "config.yaml"
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", config_file), \
                 patch("markdown_qa.config.APIConfig") as mock_api_config_class:
                # Create mock API config instance
                mock_api_config = MagicMock()
                mock_api_config.base_url = "https://api.example.com/v1"
                mock_api_config.api_key = "test-key"
                mock_api_config_class.return_value = mock_api_config

                # Create initial config
                config_file.parent.mkdir(parents=True, exist_ok=True)
                with open(config_file, "w") as f:
                    yaml.dump({
                        "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                        "server": {
                            "port": 8765,
                            "directories": [str(doc_dir)],
                            "reload_interval": 300,
                        }
                    }, f)

            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_YAML", config_file):
                from markdown_qa.config import APIConfig
                api_config = APIConfig(config_file=config_file)
                config = ServerConfig(config_file=config_file, api_config=api_config)
                original_dirs = config.directories.copy()

                # Update config file with invalid directory
                with open(config_file, "w") as f:
                    yaml.dump({
                        "api": {"base_url": "https://api.example.com/v1", "api_key": "test-key"},
                        "server": {
                            "port": 8765,
                            "directories": ["/nonexistent/directory"],
                            "reload_interval": 300,
                        }
                    }, f)

                with pytest.raises(ValueError, match="Configuration reload failed"):
                    config.reload(preserve_cli_overrides=False)

                # Original directories should be preserved
                assert config.directories == original_dirs
