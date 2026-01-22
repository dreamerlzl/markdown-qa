"""Tests for API configuration module."""

import os
import tempfile
from pathlib import Path

import pytest

from markdown_qa.config import APIConfig


class TestAPIConfig:
    """Test API configuration reading from config file and environment variables."""

    def test_read_from_config_file_yaml(self):
        """Test reading API config from YAML config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text(
                """
api:
  base_url: "https://api.example.com/v1"
  api_key: "test-key-from-file"
"""
            )
            config = APIConfig(config_file=config_path)
            assert config.base_url == "https://api.example.com/v1"
            assert config.api_key == "test-key-from-file"

    def test_read_from_config_file_toml(self):
        """Test reading API config from TOML config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                """
[api]
base_url = "https://api.example.com/v1"
api_key = "test-key-from-toml"
"""
            )
            config = APIConfig(config_file=config_path)
            assert config.base_url == "https://api.example.com/v1"
            assert config.api_key == "test-key-from-toml"

    def test_read_from_environment_variables(self):
        """Test reading API config from environment variables."""
        os.environ["MARKDOWN_QA_API_BASE_URL"] = "https://api.env.com/v1"
        os.environ["MARKDOWN_QA_API_KEY"] = "test-key-from-env"
        try:
            config = APIConfig()
            assert config.base_url == "https://api.env.com/v1"
            assert config.api_key == "test-key-from-env"
        finally:
            del os.environ["MARKDOWN_QA_API_BASE_URL"]
            del os.environ["MARKDOWN_QA_API_KEY"]

    def test_config_file_precedence_over_env_vars(self):
        """Test that config file takes precedence over environment variables."""
        os.environ["MARKDOWN_QA_API_BASE_URL"] = "https://api.env.com/v1"
        os.environ["MARKDOWN_QA_API_KEY"] = "test-key-from-env"
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                config_path = Path(tmpdir) / "config.yaml"
                config_path.write_text(
                    """
api:
  base_url: "https://api.file.com/v1"
  api_key: "test-key-from-file"
"""
                )
                config = APIConfig(config_file=config_path)
                assert config.base_url == "https://api.file.com/v1"
                assert config.api_key == "test-key-from-file"
        finally:
            del os.environ["MARKDOWN_QA_API_BASE_URL"]
            del os.environ["MARKDOWN_QA_API_KEY"]

    def test_missing_config_raises_error(self):
        """Test that missing API configuration raises an error."""
        # Clear environment variables
        env_vars = ["MARKDOWN_QA_API_BASE_URL", "MARKDOWN_QA_API_KEY"]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

        with pytest.raises(ValueError, match="API configuration is missing"):
            APIConfig()

    def test_default_config_file_location(self):
        """Test that default config file location is used if no path specified."""
        # This test checks if the default location (~/.markdown-qa/config.yaml) is checked
        # We'll test this by ensuring it tries to read from the default location
        config = APIConfig()
        # If default file doesn't exist, should fall back to env vars or raise error
        # This is a placeholder test - actual implementation will handle this
