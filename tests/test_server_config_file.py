"""Tests for server configuration from config file."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from markdown_qa.config import APIConfig
from markdown_qa.server_config import ServerConfig


class TestServerConfigFile:
    """Test server configuration reading from config file."""

    def test_load_directories_from_yaml(self):
        """Test loading directories from YAML config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_dir1 = Path(tmpdir) / "docs1"
            doc_dir2 = Path(tmpdir) / "docs2"
            doc_dir1.mkdir()
            doc_dir2.mkdir()

            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
api:
  base_url: "https://api.example.com/v1"
  api_key: "test-key"
server:
  directories:
    - "{}"
    - "{}"
""".format(
                    str(doc_dir1), str(doc_dir2)
                )
            )

            api_config = APIConfig(config_file=config_file)
            config = ServerConfig(config_file=config_file, api_config=api_config)

            assert len(config.directories) == 2
            assert str(doc_dir1) in config.directories
            assert str(doc_dir2) in config.directories

    def test_load_directories_from_yaml_string(self):
        """Test loading directories from YAML config file as comma-separated string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_dir1 = Path(tmpdir) / "docs1"
            doc_dir2 = Path(tmpdir) / "docs2"
            doc_dir1.mkdir()
            doc_dir2.mkdir()

            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
api:
  base_url: "https://api.example.com/v1"
  api_key: "test-key"
server:
  directories: "{},{}"
""".format(
                    str(doc_dir1), str(doc_dir2)
                )
            )

            api_config = APIConfig(config_file=config_file)
            config = ServerConfig(config_file=config_file, api_config=api_config)

            assert len(config.directories) == 2
            assert str(doc_dir1) in config.directories
            assert str(doc_dir2) in config.directories

    def test_load_all_settings_from_yaml(self):
        """Test loading all server settings from YAML config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
api:
  base_url: "https://api.example.com/v1"
  api_key: "test-key"
server:
  port: 9000
  directories:
    - "{}"
  reload_interval: 600
  index_name: "custom"
""".format(
                    str(doc_dir)
                )
            )

            api_config = APIConfig(config_file=config_file)
            config = ServerConfig(config_file=config_file, api_config=api_config)

            assert config.port == 9000
            assert config.directories == [str(doc_dir)]
            assert config.reload_interval == 600
            assert config.index_name == "custom"

    def test_cli_args_override_config_file(self):
        """Test that CLI arguments override config file values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_dir1 = Path(tmpdir) / "docs1"
            doc_dir2 = Path(tmpdir) / "docs2"
            doc_dir1.mkdir()
            doc_dir2.mkdir()

            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
api:
  base_url: "https://api.example.com/v1"
  api_key: "test-key"
server:
  port: 9000
  directories:
    - "{}"
  reload_interval: 600
  index_name: "config-index"
""".format(
                    str(doc_dir1)
                )
            )

            api_config = APIConfig(config_file=config_file)
            # CLI args should override config file
            config = ServerConfig(
                config_file=config_file,
                api_config=api_config,
                port=8000,
                directories=[str(doc_dir2)],
                reload_interval=120,
                index_name="cli-index",
            )

            assert config.port == 8000  # CLI overrides config file
            assert config.directories == [str(doc_dir2)]  # CLI overrides config file
            assert config.reload_interval == 120  # CLI overrides config file
            assert config.index_name == "cli-index"  # CLI overrides config file

    def test_config_file_precedence_over_env(self):
        """Test that config file takes precedence over environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_dir1 = Path(tmpdir) / "docs1"
            doc_dir2 = Path(tmpdir) / "docs2"
            doc_dir1.mkdir()
            doc_dir2.mkdir()

            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text(
                """
api:
  base_url: "https://api.example.com/v1"
  api_key: "test-key"
server:
  directories:
    - "{}"
""".format(
                    str(doc_dir1)
                )
            )

            # Set environment variable
            os.environ["MARKDOWN_QA_DIRECTORIES"] = str(doc_dir2)

            try:
                api_config = APIConfig(config_file=config_file)
                config = ServerConfig(config_file=config_file, api_config=api_config)

                # Config file should take precedence over env var
                assert config.directories == [str(doc_dir1)]
            finally:
                del os.environ["MARKDOWN_QA_DIRECTORIES"]

    def test_default_config_file_location(self):
        """Test that default config file location is checked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create default config directory structure
            config_dir = Path(tmpdir) / ".markdown-qa"
            config_dir.mkdir()
            config_file = config_dir / "config.yaml"

            doc_dir = Path(tmpdir) / "docs"
            doc_dir.mkdir()

            config_file.write_text(
                """
api:
  base_url: "https://api.example.com/v1"
  api_key: "test-key"
server:
  directories:
    - "{}"
""".format(
                    str(doc_dir)
                )
            )

            # Mock the default config path
            with patch("markdown_qa.server_config.ServerConfig.DEFAULT_CONFIG_DIR", config_dir), \
                 patch("markdown_qa.config.APIConfig.DEFAULT_CONFIG_DIR", config_dir):
                api_config = APIConfig(config_file=config_file)
                config = ServerConfig(config_file=config_file, api_config=api_config)

                assert len(config.directories) == 1
                assert str(doc_dir) in config.directories
