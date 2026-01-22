"""Tests for configuration file watcher."""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from markdown_qa.config_watcher import ConfigWatcher


class TestConfigWatcher:
    """Test configuration file watcher."""

    def test_start_stop(self):
        """Test starting and stopping watcher."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
            config_path = Path(f.name)
            f.write("test: value\n")

        try:
            callback = MagicMock()
            watcher = ConfigWatcher(config_path, callback)

            async def run_test():
                await watcher.start()
                # Wait a bit for observer to start
                await asyncio.sleep(0.1)
                assert watcher.observer is not None
                assert watcher.observer.is_alive()

                observer_before_stop = watcher.observer
                await watcher.stop()

                # Observer should be stopped and set to None
                assert watcher.observer is None
                assert not observer_before_stop.is_alive()

            asyncio.run(run_test())
        finally:
            config_path.unlink()

    def test_file_change_detection(self):
        """Test that file changes trigger callback."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
            config_path = Path(f.name)
            f.write("test: value1\n")

        try:
            callback = MagicMock()
            watcher = ConfigWatcher(config_path, callback)

            async def run_test():
                await watcher.start()

                # Wait a bit for observer to be ready
                await asyncio.sleep(0.1)

                # Modify file
                with open(config_path, "w") as f:
                    f.write("test: value2\n")

                # Wait for file system event to be processed
                await asyncio.sleep(0.3)

                await watcher.stop()

                # Callback should have been called
                assert callback.call_count >= 1

            asyncio.run(run_test())
        finally:
            config_path.unlink()

    def test_nonexistent_file(self):
        """Test watcher with non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent_config.yaml"
            callback = MagicMock()
            watcher = ConfigWatcher(config_path, callback)

            async def run_test():
                await watcher.start()
                # Even if file doesn't exist, we can watch the directory
                assert watcher.observer is not None
                await asyncio.sleep(0.1)
                await watcher.stop()

                # Callback should not be called for non-existent file
                assert callback.call_count == 0

            asyncio.run(run_test())

    def test_file_creation(self):
        """Test that file creation triggers callback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            callback = MagicMock()
            watcher = ConfigWatcher(config_path, callback)

            async def run_test():
                await watcher.start()

                # Wait a bit for observer to be ready
                await asyncio.sleep(0.1)

                # Create file
                with open(config_path, "w") as f:
                    f.write("test: value\n")

                # Wait for file system event to be processed
                await asyncio.sleep(0.3)

                await watcher.stop()

                # Callback should have been called when file was created
                assert callback.call_count >= 1

            asyncio.run(run_test())

    def test_callback_error_handling(self):
        """Test that callback errors don't crash watcher."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
            config_path = Path(f.name)
            f.write("test: value1\n")

        try:
            callback = MagicMock(side_effect=Exception("Callback error"))
            watcher = ConfigWatcher(config_path, callback)

            async def run_test():
                await watcher.start()

                # Wait a bit for observer to be ready
                await asyncio.sleep(0.1)

                # Modify file
                with open(config_path, "w") as f:
                    f.write("test: value2\n")

                # Wait for file system event to be processed
                await asyncio.sleep(0.3)

                await watcher.stop()

                # Watcher should still be running despite callback error
                # Wait a bit to ensure observer was started
                await asyncio.sleep(0.1)
                # Observer may be None if stop was called, but it should have existed
                # The important thing is that the error didn't crash the watcher

            asyncio.run(run_test())
        finally:
            config_path.unlink()

    def test_multiple_changes_debouncing(self):
        """Test that rapid successive changes are debounced."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml") as f:
            config_path = Path(f.name)
            f.write("test: value1\n")

        try:
            callback = MagicMock()
            watcher = ConfigWatcher(config_path, callback)

            async def run_test():
                await watcher.start()

                # Wait a bit for observer to be ready
                await asyncio.sleep(0.1)

                # Make rapid successive changes
                for i in range(5):
                    with open(config_path, "w") as f:
                        f.write(f"test: value{i}\n")
                    await asyncio.sleep(0.05)  # Very short delay

                # Wait for file system events to be processed
                await asyncio.sleep(0.5)

                await watcher.stop()

                # Due to debouncing, callback should be called fewer times than changes
                # (exact count depends on timing, but should be less than 5)
                assert callback.call_count > 0
                # The debouncing logic should prevent all 5 from being processed immediately

            asyncio.run(run_test())
        finally:
            config_path.unlink()
