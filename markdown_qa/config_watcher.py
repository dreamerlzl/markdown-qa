"""Configuration file watcher for hot reload."""

import asyncio
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from markdown_qa.logger import get_server_logger


class ConfigFileHandler(FileSystemEventHandler):
    """Handler for config file change events."""

    def __init__(self, config_path: Path, reload_callback: Callable[[], None]):
        """
        Initialize config file handler.

        Args:
            config_path: Path to the configuration file to watch.
            reload_callback: Callback function to call when config changes.
        """
        self.config_path = config_path
        self.reload_callback = reload_callback
        self._last_handled: Optional[float] = None
        self.logger = get_server_logger()

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification event."""
        if event.is_directory:
            return

        # Check if this is the file we're watching
        event_path = Path(str(event.src_path))
        if event_path == self.config_path:
            # Debounce rapid successive events (some editors trigger multiple events)
            import time

            current_time = time.time()
            if self._last_handled is not None and (current_time - self._last_handled) < 0.5:
                return

            self._last_handled = current_time

            self.logger.info(f"Configuration file changed: {self.config_path}")
            try:
                self.reload_callback()
                self.logger.info("Configuration reloaded successfully")
            except Exception as e:
                self.logger.error(f"Error reloading configuration: {e}", exc_info=True)

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation event (for when config file is created)."""
        if event.is_directory:
            return

        event_path = Path(str(event.src_path))
        if event_path == self.config_path:
            self.logger.info(f"Configuration file created: {self.config_path}")
            try:
                self.reload_callback()
                self.logger.info("Configuration reloaded successfully")
            except Exception as e:
                self.logger.error(f"Error reloading configuration: {e}", exc_info=True)


class ConfigWatcher:
    """Watches configuration file for changes using file system event notifications."""

    def __init__(
        self,
        config_path: Path,
        reload_callback: Callable[[], None],
    ):
        """
        Initialize config watcher.

        Args:
            config_path: Path to the configuration file to watch.
            reload_callback: Callback function to call when config changes.
        """
        self.config_path = config_path
        self.reload_callback = reload_callback
        self.observer: Optional[Any] = None
        self.event_handler: Optional[ConfigFileHandler] = None

    async def start(self) -> None:
        """Start watching the config file."""
        if self.observer is not None and self.observer.is_alive():
            return

        # Create event handler
        self.event_handler = ConfigFileHandler(self.config_path, self.reload_callback)

        # Create observer
        self.observer = Observer()

        # Watch the parent directory (watchdog watches directories, not individual files)
        watch_dir = self.config_path.parent
        if not watch_dir.exists():
            # If parent directory doesn't exist, watch the parent's parent
            watch_dir = watch_dir.parent
            if not watch_dir.exists():
                logger = get_server_logger()
                logger.warning(
                    f"Cannot watch config file {self.config_path} - parent directory does not exist"
                )
                return

        # Schedule watching the directory
        self.observer.schedule(
            self.event_handler, str(watch_dir), recursive=False
        )

        # Start observer in a thread (watchdog uses threading)
        self.observer.start()

    async def stop(self) -> None:
        """Stop watching the config file."""
        if self.observer is not None:
            self.observer.stop()
            # Wait for observer thread to finish (with timeout)
            self.observer.join(timeout=2.0)
            self.observer = None
            self.event_handler = None
