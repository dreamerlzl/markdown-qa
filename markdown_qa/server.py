"""WebSocket server module for markdown Q&A system."""

import asyncio
import json
import signal
import time
from pathlib import Path
from typing import Optional

import websockets
from websockets.server import ServerConnection

from markdown_qa.config_watcher import ConfigWatcher
from markdown_qa.index_manager import IndexManager
from markdown_qa.logger import get_server_logger
from markdown_qa.messages import (
    MessageType,
    create_error_message,
    create_status_message,
    validate_query_message,
)
from markdown_qa.query_handler import QueryHandler
from markdown_qa.reload_scheduler import ReloadScheduler
from markdown_qa.server_config import ServerConfig


class MarkdownQAServer:
    """WebSocket server for markdown Q&A system."""

    def __init__(self, config: ServerConfig):
        """
        Initialize server.

        Args:
            config: Server configuration.
        """
        self.config = config
        self.logger = get_server_logger()
        self.index_manager = IndexManager(api_config=config.api_config)
        self.query_handler = QueryHandler(
            self.index_manager, api_config=config.api_config
        )
        self.reload_scheduler: Optional[ReloadScheduler] = None
        self.config_watcher: Optional[ConfigWatcher] = None
        self._server: Optional[websockets.server.Server] = None  # type: ignore[assignment]
        self._shutdown_event = asyncio.Event()
        self._config_file_path: Optional[Path] = None

    async def _handle_client(self, websocket: ServerConnection) -> None:  # type: ignore[type-arg]
        """
        Handle a WebSocket client connection.

        Args:
            websocket: WebSocket connection.
        """
        # Handle messages
        try:
            async for message in websocket:  # type: ignore[attr-defined]
                try:
                    data = json.loads(message)
                    await self._process_message(websocket, data)
                except json.JSONDecodeError:
                    await websocket.send(  # type: ignore[attr-defined]
                        json.dumps(create_error_message("Invalid JSON format"))
                    )
                except Exception as e:
                    await websocket.send(  # type: ignore[attr-defined]
                        json.dumps(create_error_message(f"Error: {str(e)}"))
                    )
        except websockets.exceptions.ConnectionClosed:
            # Client disconnected, this is normal
            pass

    async def _process_message(
        self,
        websocket: ServerConnection,
        message: dict,  # type: ignore[type-arg]
    ) -> None:
        """
        Process a message from a client.

        Args:
            websocket: WebSocket connection.
            message: Message dictionary.
        """
        request_start = time.perf_counter()
        msg_type = message.get("type")
        self.logger.info(f"Received message: {message}")

        if msg_type == MessageType.QUERY:
            # Validate query message
            is_valid, error = validate_query_message(message)
            if not is_valid:
                await websocket.send(  # type: ignore[attr-defined]
                    json.dumps(create_error_message(error or "Invalid query"))
                )
                return

            # Handle query with streaming response
            chunk_count = 0
            try:
                for response in self.query_handler.handle_query_stream(message):
                    await websocket.send(json.dumps(response))  # type: ignore[attr-defined]
                    if response.get("type") == MessageType.STREAM_CHUNK:
                        chunk_count += 1
                        self.logger.debug(
                            f"Sent chunk: {response.get('chunk', '')[:50]}..."
                        )

                request_ms = (time.perf_counter() - request_start) * 1000
                self.logger.info(
                    f"request_completed type=query request_ms={request_ms:.2f} chunks={chunk_count}"
                )
            except Exception as e:
                # If query handling fails, send error response
                error_response = create_error_message(
                    f"Error processing query: {str(e)}"
                )
                await websocket.send(json.dumps(error_response))  # type: ignore[attr-defined]
                request_ms = (time.perf_counter() - request_start) * 1000
                self.logger.error(
                    f"request_error type=query request_ms={request_ms:.2f} error={e}",
                    exc_info=True,
                )

        elif msg_type == MessageType.STATUS:
            # Client requesting status
            if self.index_manager.is_ready():
                status = "ready"
                msg = "Server ready"
            elif self.reload_scheduler and self.reload_scheduler.is_reloading():
                status = "indexing"
                msg = "Server reloading indexes"
            else:
                status = "not_ready"
                msg = "Server loading indexes"

            await websocket.send(json.dumps(create_status_message(status, msg)))  # type: ignore[attr-defined]
            request_ms = (time.perf_counter() - request_start) * 1000
            self.logger.info(
                f"request_completed type=status request_ms={request_ms:.2f}"
            )

        else:
            await websocket.send(  # type: ignore[attr-defined]
                json.dumps(create_error_message(f"Unknown message type: {msg_type}"))
            )
            request_ms = (time.perf_counter() - request_start) * 1000
            self.logger.warning(
                f"request_completed type=unknown request_ms={request_ms:.2f} msg_type={msg_type}"
            )

    def _reload_indexes(self, force: bool = False) -> None:
        """
        Reload indexes (called by scheduler).

        Uses incremental updates when possible to only process changed files.
        Falls back to full rebuild when incremental update is not possible.

        Args:
            force: If True, rebuild even if no changes detected.
        """
        try:
            if force:
                # Force full rebuild (e.g., config changed)
                self.logger.info("Forcing full index rebuild...")
                self.index_manager._do_full_rebuild(
                    self.config.index_name, self.config.directories
                )
                self.logger.info("Full index rebuild completed successfully")
                return

            # Try incremental update
            result = self.index_manager.incremental_update(
                self.config.index_name, self.config.directories
            )

            # Check if we fell back to full rebuild
            if result.fallback_to_full_rebuild:
                self.logger.info(f"Performed full rebuild (reason: {result.reason})")
                return

            # Log incremental update results
            if not result.has_changes:
                self.logger.debug("No changes detected, skipping reload")
                return

            self.logger.info(
                f"Incremental update completed: "
                f"{len(result.added_files)} added, "
                f"{len(result.modified_files)} modified, "
                f"{len(result.deleted_files)} deleted"
            )
            if result.added_files:
                self.logger.info(f"  Added: {result.added_files}")
            if result.modified_files:
                self.logger.info(f"  Modified: {result.modified_files}")
            if result.deleted_files:
                self.logger.info(f"  Deleted: {result.deleted_files}")

        except Exception as e:
            # Log error but don't crash
            self.logger.error(f"Error reloading indexes: {e}", exc_info=True)

    def _reload_config(self) -> None:
        """Reload configuration from file (called by config watcher)."""
        try:
            # Store old directories and index_name before reload
            old_directories_set = set(
                self.config.directories.copy() if self.config.directories else []
            )
            old_index_name = self.config.index_name

            result = self.config.reload(preserve_cli_overrides=True)

            if not result.has_changes:
                return

            self.logger.info(
                f"Configuration reloaded. Changed settings: {', '.join(result.changed)}"
            )

            if result.requires_restart:
                self.logger.warning(
                    "Port change detected. Server restart required for port change to take effect."
                )
                return

            # Handle hot-reloadable changes
            if "directories" in result.changed or "index_name" in result.changed:
                # If index_name changed, always do full rebuild
                if "index_name" in result.changed:
                    self.logger.info("Index name changed, performing full rebuild...")
                    self._reload_indexes(force=True)
                elif "directories" in result.changed:
                    # Check if only directories were added (not removed)
                    # Normalize paths to absolute for comparison
                    new_directories = {
                        str(Path(d).resolve()) for d in self.config.directories
                    }

                    added_directories = new_directories - old_directories_set
                    removed_directories = old_directories_set - new_directories

                    if removed_directories:
                        # Directories were removed, need full rebuild
                        self.logger.info(
                            f"Directories removed: {removed_directories}. "
                            "Performing full rebuild..."
                        )
                        self._reload_indexes(force=True)
                    elif added_directories:
                        # Only new directories added, can use incremental update
                        self.logger.info(
                            f"New directories added: {added_directories}. "
                            "Using incremental update to index new files..."
                        )
                        # Use incremental update which will detect and index new files
                        update_result = self.index_manager.incremental_update(
                            self.config.index_name, self.config.directories
                        )

                        if update_result.fallback_to_full_rebuild:
                            self.logger.warning(
                                f"Incremental update fell back to full rebuild "
                                f"(reason: {update_result.reason})"
                            )
                        else:
                            # Update manifest with new directories
                            self.index_manager.manifest.update_index(
                                self.config.index_name, self.config.directories
                            )
                            self.logger.info(
                                f"Incremental update completed: "
                                f"{len(update_result.added_files)} files added from new directories"
                            )
                    else:
                        # Directories changed but no net additions/removals (shouldn't happen)
                        self.logger.info(
                            "Directories reordered, performing full rebuild..."
                        )
                        self._reload_indexes(force=True)

            if "reload_interval" in result.changed:
                # Restart reload scheduler with new interval
                if self.reload_scheduler:
                    self.reload_scheduler.stop()
                self.reload_scheduler = ReloadScheduler(
                    self._reload_indexes, interval=self.config.reload_interval
                )
                self.reload_scheduler.start()
                self.logger.info(
                    f"Reload scheduler updated (new interval: {self.config.reload_interval}s)"
                )

            if "api_config" in result.changed:
                # Recreate index manager and query handler with new API config
                self.logger.info("Updating API configuration...")
                self.index_manager = IndexManager(api_config=self.config.api_config)
                self.query_handler = QueryHandler(
                    self.index_manager, api_config=self.config.api_config
                )
                # Reload index with new API config
                self.logger.info("Reloading indexes with new API configuration...")
                self._reload_indexes(force=True)

        except Exception as e:
            self.logger.error(f"Error reloading configuration: {e}", exc_info=True)

    async def start(self) -> None:
        """Start the server."""
        # Load indexes at startup
        self.logger.info(f"Loading indexes for directories: {self.config.directories}")
        try:
            self.index_manager.load_index(
                self.config.index_name, self.config.directories
            )
        except Exception as e:
            self.logger.error(f"Error loading indexes: {e}", exc_info=True)
            raise RuntimeError(f"Failed to load indexes: {e}") from e

        if not self.index_manager.is_ready():
            raise RuntimeError("Failed to load indexes at startup")

        self.logger.info("Indexes loaded successfully")

        # Start reload scheduler
        self.reload_scheduler = ReloadScheduler(
            self._reload_indexes, interval=self.config.reload_interval
        )
        self.reload_scheduler.start()
        self.logger.info(
            f"Reload scheduler started (interval: {self.config.reload_interval}s)"
        )

        # Start config file watcher for hot reload
        self._config_file_path = self.config.get_config_file_path()
        if self._config_file_path:
            self.config_watcher = ConfigWatcher(
                self._config_file_path, self._reload_config
            )
            await self.config_watcher.start()
            self.logger.info(
                f"Configuration file watcher started: {self._config_file_path}"
            )

        # Start WebSocket server
        self.logger.info(f"Starting WebSocket server on port {self.config.port}")
        self._server = await websockets.serve(  # type: ignore[assignment,invalid-argument-type]
            self._handle_client, host="0.0.0.0", port=self.config.port
        )

        self.logger.info(
            f"Server ready and listening on ws://localhost:{self.config.port}"
        )

        # In websockets 16.0+, we need to call serve_forever() to actually start serving
        # Create a task that will be cancelled when shutdown is requested
        serve_task = asyncio.create_task(self._server.serve_forever())  # type: ignore[attr-defined]

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Cancel the serve task when shutting down
        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Stop the server gracefully."""
        self.logger.info("Shutting down server...")

        # Stop config watcher
        if self.config_watcher:
            await self.config_watcher.stop()

        # Stop reload scheduler
        if self.reload_scheduler:
            self.reload_scheduler.stop()

        # Close WebSocket server
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        self.logger.info("Server stopped")

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()

        def signal_handler():
            loop.call_soon_threadsafe(self._shutdown_event.set)

        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())

    async def run(self) -> None:
        """Run the server (main entry point)."""
        self._setup_signal_handlers()

        try:
            await self.start()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.logger.error(f"Fatal error starting server: {e}", exc_info=True)
            raise
        finally:
            await self.stop()


async def main() -> None:
    """Main entry point for server."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Markdown Q&A Server",
        epilog="""
Configuration precedence (highest to lowest):
  1. Command-line arguments
  2. Config file (~/.md-qa/config.yaml or config.toml)
  3. Environment variables
  4. Defaults

Config file format (YAML):
  api:
    base_url: "https://api.example.com/v1"
    api_key: "your-api-key"
  server:
    port: 8765
    directories:
      - /path/to/docs1
      - /path/to/docs2
    reload_interval: 300
    index_name: "default"
        """,
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="WebSocket server port (overrides config file, default: 8765)",
    )
    parser.add_argument(
        "--directories",
        type=str,
        nargs="+",
        default=None,
        help="Directories to index (space-separated, overrides config file)",
    )
    parser.add_argument(
        "--reload-interval",
        type=int,
        default=None,
        help="Index reload interval in seconds (overrides config file, default: 300)",
    )
    parser.add_argument(
        "--index-name",
        type=str,
        default=None,
        help="Index name (overrides config file, default: 'default')",
    )

    args = parser.parse_args()

    # Create server configuration
    # None values allow ServerConfig to check config file
    config = ServerConfig(
        port=args.port,
        directories=args.directories,
        reload_interval=args.reload_interval,
        index_name=args.index_name,
    )

    # Create and run server
    server = MarkdownQAServer(config)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
