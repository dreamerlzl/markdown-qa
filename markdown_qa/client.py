"""CLI client module for connecting to WebSocket server."""

import asyncio
import json
import sys
from typing import Any, AsyncContextManager, Dict, Optional

import websockets
from websockets.client import ClientConnection
from websockets.exceptions import (
    ConnectionClosed,
    InvalidHandshake,
    InvalidStatus,
    InvalidURI,
)

from markdown_qa.formatter import ResponseFormatter
from markdown_qa.logger import get_client_logger
from markdown_qa.messages import (
    MessageType,
    create_query_message,
)


class MarkdownQAClient:
    """CLI client for markdown Q&A server."""

    def __init__(self, server_url: str = "ws://localhost:8765"):
        """
        Initialize client.

        Args:
            server_url: WebSocket server URL (default: ws://localhost:8765).
        """
        self.server_url = server_url
        self.websocket: Optional[ClientConnection] = None
        self._connection: Optional[AsyncContextManager[ClientConnection]] = None
        self.formatter = ResponseFormatter()
        self.logger = get_client_logger()

    async def connect(self) -> bool:
        """
        Connect to the WebSocket server.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            # In websockets 16.0+, connect() returns an async context manager
            # We need to store it and enter it to get the connection
            # The context manager handles the connection lifecycle
            connection_cm = websockets.connect(self.server_url)
            # Store the context manager for proper cleanup
            self._connection = connection_cm
            # Enter the context manager to establish the connection
            # This performs the WebSocket handshake
            self.websocket = await connection_cm.__aenter__()  # type: ignore[attr-defined]
            return True
        except (ConnectionRefusedError, OSError) as e:
            self.logger.error(f"Failed to connect to server at {self.server_url}: {e}")
            self.logger.info("\nMake sure the server is running:")
            self.logger.info("  md-qa server --directories /path/to/docs")
            self.logger.info(
                "  or: python -m markdown_qa.server --directories /path/to/docs"
            )
            return False
        except (InvalidURI, InvalidHandshake, InvalidStatus) as e:
            self.logger.error(f"Failed to connect to server at {self.server_url}: {e}")
            self.logger.info("\nPossible causes:")
            self.logger.info("  - Server is not running")
            self.logger.info("  - Wrong port or URL")
            self.logger.info("  - Server is not a WebSocket server")
            self.logger.info("\nMake sure the server is running:")
            self.logger.info("  md-qa server --directories /path/to/docs")
            self.logger.info(
                "  or: python -m markdown_qa.server --directories /path/to/docs"
            )
            return False
        except Exception as e:
            # Catch any other websockets exceptions
            error_msg = str(e)
            if (
                "did not receive a valid HTTP response" in error_msg
                or "HTTP" in error_msg
            ):
                self.logger.error(
                    f"Failed to connect to server at {self.server_url}: {error_msg}"
                )
                self.logger.info("\nThis usually means:")
                self.logger.info("  - The server is not running")
                self.logger.info(
                    "  - The server is running but not on the expected port"
                )
                self.logger.info(
                    "  - Something else is using that port (not a WebSocket server)"
                )
                self.logger.info("\nMake sure the server is running:")
                self.logger.info("  md-qa server --directories /path/to/docs")
                self.logger.info(
                    "  or: python -m markdown_qa.server --directories /path/to/docs"
                )
            else:
                self.logger.error(
                    f"Failed to connect to server at {self.server_url}: {error_msg}"
                )
                self.logger.info("\nMake sure the server is running:")
                self.logger.info("  md-qa server --directories /path/to/docs")
                self.logger.info(
                    "  or: python -m markdown_qa.server --directories /path/to/docs"
                )
            return False

    async def disconnect(self) -> None:
        """Disconnect from the server."""
        if self._connection and self.websocket:
            # Properly exit the async context manager
            try:
                await self._connection.__aexit__(None, None, None)  # type: ignore[attr-defined]
            except Exception:
                # If context manager exit fails, try to close directly
                try:
                    await self.websocket.close()  # type: ignore[attr-defined]
                except Exception:
                    pass
            self.websocket = None
            self._connection = None
        elif self.websocket:
            # Fallback: close directly if no context manager
            try:
                await self.websocket.close()  # type: ignore[attr-defined]
            except Exception:
                pass
            self.websocket = None

    async def send_query(
        self, question: str, index: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a query to the server.

        Args:
            question: The question to ask.
            index: Optional index name.

        Returns:
            Response dictionary from server.

        Raises:
            RuntimeError: If not connected or connection error occurs.
        """
        if not self.websocket:
            raise RuntimeError("Not connected to server")

        # Create and send query message
        query_msg = create_query_message(question, index=index)
        await self.websocket.send(json.dumps(query_msg))  # type: ignore[attr-defined]

        # Wait for response with timeout
        try:
            # Use asyncio.wait_for to add a timeout for long-running queries
            response_text = await asyncio.wait_for(
                self.websocket.recv(),  # type: ignore[attr-defined]
                timeout=300.0,  # 5 minute timeout for query processing
            )
            response = json.loads(response_text)
            return response
        except asyncio.TimeoutError:
            raise RuntimeError(
                "Query timed out - server did not respond within 5 minutes"
            )
        except ConnectionClosed:
            raise RuntimeError("Connection closed by server")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid response from server: {e}")

    async def send_query_stream(
        self, question: str, index: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a query to the server and stream the response.

        Prints answer chunks as they arrive, then returns the final result.

        Args:
            question: The question to ask.
            index: Optional index name.

        Returns:
            Final response with complete answer and sources.

        Raises:
            RuntimeError: If not connected or connection error occurs.
        """
        if not self.websocket:
            raise RuntimeError("Not connected to server")

        # Create and send query message
        query_msg = create_query_message(question, index=index)
        await self.websocket.send(json.dumps(query_msg))  # type: ignore[attr-defined]

        # Collect the full answer and sources
        full_answer = ""
        sources: list[str] = []

        try:
            while True:
                response_text = await asyncio.wait_for(
                    self.websocket.recv(),  # type: ignore[attr-defined]
                    timeout=300.0,
                )
                response = json.loads(response_text)
                msg_type = response.get("type")

                if msg_type == MessageType.STREAM_START:
                    # Stream starting, nothing to display yet
                    continue
                elif msg_type == MessageType.STREAM_CHUNK:
                    # Print chunk immediately without newline
                    chunk = response.get("chunk", "")
                    print(chunk, end="", flush=True)
                    full_answer += chunk
                elif msg_type == MessageType.STREAM_END:
                    # Stream complete, print newline and get sources
                    print()  # Final newline
                    sources = response.get("sources", [])
                    break
                elif msg_type == MessageType.ERROR:
                    # Error occurred
                    return response
                elif msg_type == MessageType.RESPONSE:
                    # Non-streaming response (fallback)
                    return response
                else:
                    self.logger.warning(f"Unknown message type during stream: {msg_type}")

            # Return constructed response
            return {
                "type": MessageType.RESPONSE,
                "answer": full_answer,
                "sources": sources,
            }

        except asyncio.TimeoutError:
            raise RuntimeError(
                "Query timed out - server did not respond within 5 minutes"
            )
        except ConnectionClosed:
            raise RuntimeError("Connection closed by server")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid response from server: {e}")

    async def get_status(self) -> Dict[str, Any]:
        """
        Get server status.

        Returns:
            Status message dictionary.
        """
        if not self.websocket:
            raise RuntimeError("Not connected to server")

        # Send status request
        status_msg = {"type": MessageType.STATUS}
        await self.websocket.send(json.dumps(status_msg))  # type: ignore[attr-defined]

        # Wait for status response
        try:
            response_text = await self.websocket.recv()  # type: ignore[attr-defined]
            response = json.loads(response_text)
            return response
        except ConnectionClosed:
            raise RuntimeError("Connection closed by server")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid response from server: {e}")

    def display_response(self, response: Dict[str, Any]) -> None:
        """
        Display a response from the server.

        Args:
            response: Response dictionary from server.
        """
        msg_type = response.get("type")

        if msg_type == MessageType.RESPONSE:
            answer = response.get("answer", "")
            sources = response.get("sources", [])

            # Format and display
            display_text = self.formatter.format_for_display(answer, sources)
            print(display_text)  # Keep print for user-facing output

        elif msg_type == MessageType.ERROR:
            error_msg = response.get("message", "Unknown error")
            self.logger.error(f"Error: {error_msg}")
            print(
                f"Error: {error_msg}", file=sys.stderr
            )  # Also print to stderr for user

        elif msg_type == MessageType.STATUS:
            status = response.get("status", "")
            message = response.get("message", "")
            if message:
                self.logger.info(f"Status: {status} - {message}")
                print(f"Status: {status} - {message}")
            else:
                self.logger.info(f"Status: {status}")
                print(f"Status: {status}")

        else:
            self.logger.warning(f"Unknown response type: {msg_type}")
            print(f"Unknown response type: {msg_type}", file=sys.stderr)

    async def run_single_query(self, question: str, index: Optional[str] = None) -> int:
        """
        Run a single query and exit.

        Args:
            question: The question to ask.
            index: Optional index name.

        Returns:
            Exit code (0 for success, 1 for error).
        """
        try:
            # Connect to server
            if not await self.connect():
                return 1

            # Check server status
            try:
                status = await self.get_status()
                if status.get("status") == "not_ready":
                    self.logger.warning("Server is not ready yet. Query may fail.")
                self.logger.info(f"Server status: {status.get('status', 'unknown')}")
            except Exception:
                # Ignore status check errors, try query anyway
                self.logger.error("Error checking server status", exc_info=True)
                pass

            # Send query with streaming
            try:
                response = await self.send_query_stream(question, index=index)
            except Exception as e:
                self.logger.error(f"Error sending query: {e}", exc_info=True)
                print(f"Error sending query: {str(e)}", file=sys.stderr)
                return 1

            # Check if response was an error
            if response.get("type") == MessageType.ERROR:
                error_msg = response.get("message", "Unknown error")
                print(f"Error: {error_msg}", file=sys.stderr)
                return 1

            # Display sources (answer was already streamed)
            sources = response.get("sources", [])
            if sources:
                print()  # Blank line before sources
                formatted_sources = self.formatter.format_sources(sources)
                print(formatted_sources)

            return 0

        except Exception as e:
            self.logger.error(f"Error: {e}", exc_info=True)
            print(f"Error: {str(e)}", file=sys.stderr)
            return 1
        finally:
            await self.disconnect()

    async def run_interactive(self) -> int:
        """
        Run in interactive mode (repeated prompts).

        Returns:
            Exit code (0 for success, 1 for error).
        """
        try:
            # Connect to server
            self.logger.info(f"Connecting to {self.server_url}...")
            print(f"Connecting to {self.server_url}...")
            if not await self.connect():
                return 1

            # Get initial status
            try:
                status = await self.get_status()
                self.display_response(status)
            except Exception:
                self.logger.warning("Connected (status check failed)")
                print("Connected (status check failed)", file=sys.stderr)

            print(
                "\nEnter questions (type 'quit' or 'exit' to stop, Ctrl+C to interrupt):\n"
            )

            # Interactive loop
            while True:
                try:
                    # Get question from user
                    question = input("Question: ").strip()

                    if not question:
                        continue

                    if question.lower() in ("quit", "exit", "q"):
                        self.logger.info("User exited interactive mode")
                        print("Goodbye!")
                        break

                    # Send query with streaming
                    print()  # Blank line before response
                    response = await self.send_query_stream(question)

                    # Handle error or display sources
                    if response.get("type") == MessageType.ERROR:
                        error_msg = response.get("message", "Unknown error")
                        print(f"Error: {error_msg}", file=sys.stderr)
                    else:
                        # Display sources (answer was already streamed)
                        sources = response.get("sources", [])
                        if sources:
                            print()  # Blank line before sources
                            formatted_sources = self.formatter.format_sources(sources)
                            print(formatted_sources)
                    print()  # Blank line after response

                except KeyboardInterrupt:
                    self.logger.info("User interrupted interactive mode")
                    print("\n\nInterrupted. Goodbye!")
                    break
                except Exception as e:
                    self.logger.error(f"Error: {e}", exc_info=True)
                    print(f"Error: {str(e)}", file=sys.stderr)
                    print()  # Blank line

            return 0

        except Exception as e:
            self.logger.error(f"Error: {e}", exc_info=True)
            print(f"Error: {str(e)}", file=sys.stderr)
            return 1
        finally:
            await self.disconnect()


async def main() -> int:
    """Main entry point for CLI client."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Markdown Q&A CLI Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single question mode
  md-qa "What is Python?"

  # Interactive mode
  md-qa

  # Custom server
  md-qa --server ws://localhost:9000 "What is Python?"
        """,
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Question to ask (optional, if omitted runs in interactive mode)",
    )
    parser.add_argument(
        "--server",
        type=str,
        default="ws://localhost:8765",
        help="WebSocket server URL (default: ws://localhost:8765)",
    )
    parser.add_argument(
        "--index",
        type=str,
        help="Index name to query (optional)",
    )

    args = parser.parse_args()

    # Create client
    client = MarkdownQAClient(server_url=args.server)

    # Run in single query or interactive mode
    if args.question:
        return await client.run_single_query(args.question, index=args.index)
    else:
        return await client.run_interactive()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
