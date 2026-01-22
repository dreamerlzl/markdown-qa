"""Periodic reload scheduler module."""

import threading
import time
from typing import Callable, Optional


class ReloadScheduler:
    """Schedules periodic index reloads."""

    def __init__(
        self,
        reload_func: Callable[[], None],
        interval: int = 300,  # 5 minutes default
    ):
        """
        Initialize reload scheduler.

        Args:
            reload_func: Function to call for reloading indexes.
            interval: Reload interval in seconds (default: 300).
        """
        self.reload_func = reload_func
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_reloading = False
        self._reload_lock = threading.Lock()

    def start(self) -> None:
        """Start the reload scheduler."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the reload scheduler."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def _run(self) -> None:
        """Run the reload loop."""
        while not self._stop_event.is_set():
            # Wait for interval or until stop event
            if self._stop_event.wait(self.interval):
                break

            # Perform reload if not already reloading
            with self._reload_lock:
                if not self._is_reloading:
                    self._is_reloading = True
                    try:
                        self.reload_func()
                    except Exception:
                        # Log error but continue scheduling
                        pass
                    finally:
                        self._is_reloading = False

    def is_reloading(self) -> bool:
        """
        Check if a reload is currently in progress.

        Returns:
            True if reloading, False otherwise.
        """
        with self._reload_lock:
            return self._is_reloading
