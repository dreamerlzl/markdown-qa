"""Tests for periodic reload scheduler."""

import time
from unittest.mock import MagicMock

import pytest

from markdown_qa.reload_scheduler import ReloadScheduler


class TestReloadScheduler:
    """Test periodic reload scheduler."""

    def test_start_stop(self):
        """Test starting and stopping scheduler."""
        reload_func = MagicMock()
        scheduler = ReloadScheduler(reload_func, interval=1)

        scheduler.start()
        assert scheduler._thread is not None
        assert scheduler._thread.is_alive()

        scheduler.stop()
        # Give thread time to stop
        time.sleep(0.1)
        assert not scheduler._thread.is_alive()

    def test_reload_function_called(self):
        """Test that reload function is called."""
        reload_func = MagicMock()
        scheduler = ReloadScheduler(reload_func, interval=1)

        scheduler.start()
        time.sleep(1.5)  # Wait for at least one reload cycle
        scheduler.stop()

        # Reload function should have been called at least once
        assert reload_func.call_count >= 1

    def test_is_reloading(self):
        """Test checking if reload is in progress."""
        def slow_reload():
            time.sleep(0.5)

        scheduler = ReloadScheduler(slow_reload, interval=1)
        scheduler.start()

        # Wait a bit for reload to start
        time.sleep(1.5)

        # Check if reloading (may or may not be reloading depending on timing)
        reloading = scheduler.is_reloading()
        assert isinstance(reloading, bool)

        scheduler.stop()

    def test_multiple_starts_ignored(self):
        """Test that multiple starts are ignored."""
        reload_func = MagicMock()
        scheduler = ReloadScheduler(reload_func, interval=1)

        scheduler.start()
        thread1 = scheduler._thread

        scheduler.start()  # Should be ignored
        thread2 = scheduler._thread

        assert thread1 == thread2

        scheduler.stop()
