"""Markdown file loader module for loading markdown files from directories."""

import hashlib
import warnings
from pathlib import Path
from typing import List, Tuple


def load_markdown_files(directories: List[str]) -> List[Tuple[Path, str]]:
    """
    Load all markdown files from specified directories recursively.

    Args:
        directories: List of directory paths to search for markdown files.

    Returns:
        List of tuples containing (file_path, content) for each markdown file.

    Raises:
        ValueError: If a directory doesn't exist or no markdown files are found.
    """
    markdown_files: List[Tuple[Path, str]] = []
    errors: List[str] = []

    for directory_str in directories:
        directory = Path(directory_str)
        if not directory.exists():
            errors.append(f"Directory does not exist: {directory}")
            continue

        if not directory.is_dir():
            errors.append(f"Path is not a directory: {directory}")
            continue

        # Find all .md files recursively
        md_files = list(directory.rglob("*.md"))
        if not md_files:
            warnings.warn(f"No markdown files found in directory: {directory}")
            continue

        # Load content from each markdown file
        for md_file in md_files:
            try:
                content = md_file.read_text(encoding="utf-8")
                markdown_files.append((md_file, content))
            except Exception as e:
                warnings.warn(f"Failed to read file {md_file}: {e}")
                continue

    if not markdown_files and errors:
        raise ValueError(
            f"Failed to load any markdown files. Errors: {'; '.join(errors)}"
        )

    return markdown_files


def compute_directories_checksum(directories: List[str]) -> str:
    """
    Compute a checksum for markdown files in directories.

    The checksum is based on file paths and modification times, so it will
    change when files are added, removed, or modified.

    Args:
        directories: List of directory paths to compute checksum for.

    Returns:
        A hex digest string representing the current state of markdown files.
    """
    file_info: List[Tuple[str, float]] = []

    for directory_str in directories:
        directory = Path(directory_str)
        if not directory.exists() or not directory.is_dir():
            continue

        # Find all .md files recursively
        for md_file in directory.rglob("*.md"):
            try:
                mtime = md_file.stat().st_mtime
                # Use relative path from directory for consistency
                rel_path = str(md_file.relative_to(directory))
                file_info.append((f"{directory_str}:{rel_path}", mtime))
            except (OSError, ValueError):
                continue

    # Sort for consistent ordering
    file_info.sort(key=lambda x: x[0])

    # Create checksum from file paths and mtimes
    hasher = hashlib.sha256()
    for path, mtime in file_info:
        hasher.update(f"{path}:{mtime}".encode("utf-8"))

    return hasher.hexdigest()
