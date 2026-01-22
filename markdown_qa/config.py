"""API configuration module for reading settings from config file or environment variables."""

import os
from pathlib import Path
from typing import Optional

import yaml

try:
    import tomli  # type: ignore[import-not-found]
except ImportError:
    tomli = None


class APIConfig:
    """Manages API configuration from config file or environment variables."""

    DEFAULT_CONFIG_DIR = Path.home() / ".markdown-qa"
    DEFAULT_CONFIG_YAML = DEFAULT_CONFIG_DIR / "config.yaml"
    DEFAULT_CONFIG_TOML = DEFAULT_CONFIG_DIR / "config.toml"

    def __init__(self, config_file: Optional[Path] = None):
        """
        Initialize API configuration.

        Args:
            config_file: Optional path to config file. If not provided, checks
                        default locations and environment variables.
        """
        self.base_url: Optional[str] = None
        self.api_key: Optional[str] = None
        self.embedding_model: Optional[str] = None

        # Try to load from config file first
        if config_file:
            self._load_from_file(config_file)
        else:
            # Try default config file locations
            if self.DEFAULT_CONFIG_YAML.exists():
                self._load_from_file(self.DEFAULT_CONFIG_YAML)
            elif self.DEFAULT_CONFIG_TOML.exists():
                self._load_from_file(self.DEFAULT_CONFIG_TOML)

        # Fall back to environment variables if not set from config file
        if not self.base_url:
            self.base_url = os.environ.get("MARKDOWN_QA_API_BASE_URL")
        if not self.api_key:
            self.api_key = os.environ.get("MARKDOWN_QA_API_KEY")
        if not self.embedding_model:
            self.embedding_model = os.environ.get("MARKDOWN_QA_EMBEDDING_MODEL")

        # Set default embedding model if not specified
        if not self.embedding_model:
            self.embedding_model = "text-embedding-3-small"

        # Validate that we have required configuration
        if not self.base_url or not self.api_key:
            raise ValueError(
                "API configuration is missing. Please set either:\n"
                "- Config file at ~/.markdown-qa/config.yaml or config.toml with 'api.base_url' and 'api.api_key'\n"
                "- Environment variables MARKDOWN_QA_API_BASE_URL and MARKDOWN_QA_API_KEY"
            )

    def _load_from_file(self, config_path: Path) -> None:
        """Load configuration from YAML or TOML file."""
        if not config_path.exists():
            return

        if config_path.suffix == ".yaml" or config_path.suffix == ".yml":
            self._load_from_yaml(config_path)
        elif config_path.suffix == ".toml":
            if tomli is None:
                raise ImportError(
                    "tomli is required for TOML config files. Install it with: pip install tomli"
                )
            self._load_from_toml(config_path)

    def _load_from_yaml(self, config_path: Path) -> None:
        """Load configuration from YAML file."""
        with open(config_path) as f:
            config = yaml.safe_load(f)
            if config and "api" in config:
                self.base_url = config["api"].get("base_url") or self.base_url
                self.api_key = config["api"].get("api_key") or self.api_key
                self.embedding_model = config["api"].get("embedding_model") or self.embedding_model

    def _load_from_toml(self, config_path: Path) -> None:
        """Load configuration from TOML file."""
        with open(config_path, "rb") as f:
            config = tomli.load(f)  # type: ignore[possibly-missing-attribute]
            if config and "api" in config:
                self.base_url = config["api"].get("base_url") or self.base_url
                self.api_key = config["api"].get("api_key") or self.api_key
                self.embedding_model = config["api"].get("embedding_model") or self.embedding_model