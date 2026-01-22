"""Server configuration module."""

import os
from pathlib import Path
from typing import List, Optional

import yaml

from markdown_qa.config import APIConfig
from markdown_qa.loader import count_markdown_files
from markdown_qa.logger import get_server_logger

try:
    import tomli  # type: ignore[import-not-found]
except ImportError:
    tomli = None


class ServerConfig:
    """Manages server configuration."""

    DEFAULT_CONFIG_DIR = Path.home() / ".markdown-qa"
    DEFAULT_CONFIG_YAML = DEFAULT_CONFIG_DIR / "config.yaml"
    DEFAULT_CONFIG_TOML = DEFAULT_CONFIG_DIR / "config.toml"

    def __init__(
        self,
        port: Optional[int] = None,
        directories: Optional[List[str]] = None,
        reload_interval: Optional[int] = None,
        api_config: Optional[APIConfig] = None,
        index_name: Optional[str] = None,
        config_file: Optional[Path] = None,
    ):
        """
        Initialize server configuration.

        Args:
            port: WebSocket server port. If None, reads from config file or uses default (8765).
            directories: List of directories to index. If None, reads from config file or env var.
            reload_interval: Index reload interval in seconds. If None, reads from config file or uses default (300).
            api_config: API configuration. If None, creates from defaults.
            index_name: Name of the index to use. If None, reads from config file or uses default ("default").
            config_file: Optional path to config file. If None, checks default locations.
        """
        # Track which settings were provided via CLI args (should be preserved on reload)
        self._cli_overrides: set = set()
        if port is not None:
            self._cli_overrides.add("port")
        if directories is not None:
            self._cli_overrides.add("directories")
        if reload_interval is not None:
            self._cli_overrides.add("reload_interval")
        if index_name is not None:
            self._cli_overrides.add("index_name")
        if api_config is not None:
            self._cli_overrides.add("api_config")

        # Load from config file first (if not provided via CLI args)
        config_data = self._load_config_file(config_file)

        # Set values with precedence: CLI args > config file > env vars > defaults
        self.port = port if port is not None else (config_data.get("port") or 8765)
        self.directories = (
            directories
            if directories is not None
            else (config_data.get("directories") or self._get_directories_from_env())
        )
        self.reload_interval = (
            reload_interval
            if reload_interval is not None
            else (config_data.get("reload_interval") or 300)
        )
        self.index_name = (
            index_name if index_name is not None else (config_data.get("index_name") or "default")
        )

        if api_config is None:
            api_config = APIConfig(config_file=config_file)
        self.api_config = api_config

        # Validate configuration
        self._validate()

    def _load_config_file(self, config_file: Optional[Path] = None) -> dict:
        """
        Load server configuration from config file.

        Args:
            config_file: Optional path to config file. If None, checks default locations.

        Returns:
            Dictionary with server configuration values.
        """
        config_data: dict = {}

        # Determine which config file to use
        if config_file:
            config_path = config_file
        elif self.DEFAULT_CONFIG_YAML.exists():
            config_path = self.DEFAULT_CONFIG_YAML
        elif self.DEFAULT_CONFIG_TOML.exists():
            config_path = self.DEFAULT_CONFIG_TOML
        else:
            return config_data

        if not config_path.exists():
            return config_data

        # Load from YAML or TOML
        if config_path.suffix in (".yaml", ".yml"):
            config_data = self._load_from_yaml(config_path)
        elif config_path.suffix == ".toml":
            config_data = self._load_from_toml(config_path)

        return config_data

    def _load_from_yaml(self, config_path: Path) -> dict:
        """Load server configuration from YAML file."""
        config_data: dict = {}
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
                if config and "server" in config:
                    server_config = config["server"]
                    if "port" in server_config:
                        config_data["port"] = server_config["port"]
                    if "directories" in server_config:
                        dirs = server_config["directories"]
                        if isinstance(dirs, list):
                            config_data["directories"] = dirs
                        elif isinstance(dirs, str):
                            # Support comma-separated string
                            config_data["directories"] = [d.strip() for d in dirs.split(",") if d.strip()]
                    if "reload_interval" in server_config:
                        config_data["reload_interval"] = server_config["reload_interval"]
                    if "index_name" in server_config:
                        config_data["index_name"] = server_config["index_name"]
        except Exception:
            # If loading fails, return empty dict
            pass
        return config_data

    def _load_from_toml(self, config_path: Path) -> dict:
        """Load server configuration from TOML file."""
        config_data: dict = {}
        if tomli is None:
            return config_data
        try:
            with open(config_path, "rb") as f:
                config = tomli.load(f)  # type: ignore[possibly-missing-attribute]
                if config and "server" in config:
                    server_config = config["server"]
                    if "port" in server_config:
                        config_data["port"] = server_config["port"]
                    if "directories" in server_config:
                        dirs = server_config["directories"]
                        if isinstance(dirs, list):
                            config_data["directories"] = dirs
                        elif isinstance(dirs, str):
                            # Support comma-separated string
                            config_data["directories"] = [d.strip() for d in dirs.split(",") if d.strip()]
                    if "reload_interval" in server_config:
                        config_data["reload_interval"] = server_config["reload_interval"]
                    if "index_name" in server_config:
                        config_data["index_name"] = server_config["index_name"]
        except Exception:
            # If loading fails, return empty dict
            pass
        return config_data

    def _get_directories_from_env(self) -> List[str]:
        """Get directories from environment variable."""
        dirs_str = os.environ.get("MARKDOWN_QA_DIRECTORIES", "")
        if dirs_str:
            return [d.strip() for d in dirs_str.split(",") if d.strip()]
        return []

    def _validate(self) -> None:
        """Validate server configuration."""
        logger = get_server_logger()

        if not self.directories:
            raise ValueError(
                "No directories specified. Set MARKDOWN_QA_DIRECTORIES environment variable "
                "or provide directories in configuration."
            )

        # Validate each directory and check markdown file counts
        valid_directories: List[str] = []
        for directory in self.directories:
            if not Path(directory).exists():
                raise ValueError(f"Directory does not exist: {directory}")

            # Count markdown files in this directory
            file_count = count_markdown_files(directory)

            if file_count > 1000:
                logger.error(
                    f"Directory '{directory}' contains {file_count} markdown files "
                    f"(>1000). Skipping this directory to prevent performance issues."
                )
                continue
            elif file_count > 100:
                logger.warning(
                    f"Directory '{directory}' contains {file_count} markdown files "
                    f"(>100). This may impact performance."
                )

            valid_directories.append(directory)

        # Update directories to only include valid ones
        if not valid_directories:
            raise ValueError(
                "No valid directories remaining after validation. "
                "All directories were skipped due to having too many files (>1000)."
            )

        self.directories = valid_directories

        if self.port < 1 or self.port > 65535:
            raise ValueError(f"Invalid port number: {self.port}")

        if self.reload_interval < 1:
            raise ValueError(f"Invalid reload interval: {self.reload_interval}")

        # Validate API configuration
        if not self.api_config.base_url or not self.api_config.api_key:
            raise ValueError("API configuration is missing")

    def get_config_file_path(self) -> Optional[Path]:
        """
        Get the path to the config file being used.

        Returns:
            Path to config file, or None if no config file is used.
        """
        if self.DEFAULT_CONFIG_YAML.exists():
            return self.DEFAULT_CONFIG_YAML
        elif self.DEFAULT_CONFIG_TOML.exists():
            return self.DEFAULT_CONFIG_TOML
        return None

    def reload(self, preserve_cli_overrides: bool = True) -> dict:
        """
        Reload configuration from config file.

        Args:
            preserve_cli_overrides: If True, preserve values that were set via CLI args.

        Returns:
            Dictionary with changed settings: {'changed': [...], 'requires_restart': bool}
        """
        old_config = {
            "directories": self.directories.copy() if self.directories else [],
            "reload_interval": self.reload_interval,
            "index_name": self.index_name,
            "port": self.port,
        }

        # Reload from config file
        config_file = self.get_config_file_path()
        if not config_file:
            return {"changed": [], "requires_restart": False}

        config_data = self._load_config_file(config_file)

        # Update values (respect preserve_cli_overrides)
        changed = []
        requires_restart = False

        # Helper to check if a setting should be updated
        def should_update(setting: str) -> bool:
            """Return True if the setting should be updated from config file."""
            if not preserve_cli_overrides:
                return True
            # When preserving CLI overrides, only skip if the setting was CLI-provided
            return setting not in self._cli_overrides

        # Port changes require restart
        if "port" in config_data:
            new_port = config_data.get("port", self.port)
            if new_port != self.port:
                changed.append("port")
                requires_restart = True
                # Port changes are deferred until restart, only apply if not CLI-provided
                if should_update("port"):
                    self.port = new_port

        # Directories can be hot-reloaded
        if "directories" in config_data:
            new_directories = config_data.get("directories") or self._get_directories_from_env()
            if new_directories != self.directories:
                changed.append("directories")
                if should_update("directories"):
                    self.directories = new_directories

        # Reload interval can be hot-reloaded
        if "reload_interval" in config_data:
            new_reload_interval = config_data.get("reload_interval", self.reload_interval)
            if new_reload_interval != self.reload_interval:
                changed.append("reload_interval")
                if should_update("reload_interval"):
                    self.reload_interval = new_reload_interval

        # Index name can be hot-reloaded
        if "index_name" in config_data:
            new_index_name = config_data.get("index_name", self.index_name)
            if new_index_name != self.index_name:
                changed.append("index_name")
                if should_update("index_name"):
                    self.index_name = new_index_name

        # Reload API config
        if config_file:
            try:
                new_api_config = APIConfig(config_file=config_file)
                if (
                    new_api_config.base_url != self.api_config.base_url
                    or new_api_config.api_key != self.api_config.api_key
                ):
                    changed.append("api_config")
                    if should_update("api_config"):
                        self.api_config = new_api_config
            except Exception:
                # If API config reload fails, keep existing
                pass

        # Validate if we changed anything
        if changed:
            try:
                self._validate()
            except ValueError as e:
                # Validation failed, revert changes
                self.directories = old_config["directories"]
                self.reload_interval = old_config["reload_interval"]
                self.index_name = old_config["index_name"]
                self.port = old_config["port"]
                raise ValueError(f"Configuration reload failed validation: {e}")

        return {"changed": changed, "requires_restart": requires_restart}
