"""Markdown file loader module for loading markdown files from directories."""

import hashlib
import warnings
from pathlib import Path
from typing import Dict, List, Tuple


def count_markdown_files(directory: str) -> int:
    """
    Count the number of markdown files in a directory recursively.

    Args:
        directory: Path to directory to count markdown files in.

    Returns:
        Number of markdown files found, or 0 if directory doesn't exist.
    """
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        return 0
    return len(list(dir_path.rglob("*.md")))


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


def get_file_mtimes(directories: List[str]) -> Dict[str, float]:
    """
    Get modification times for all markdown files in directories.

    Args:
        directories: List of directory paths to scan.

    Returns:
        Dict mapping absolute file paths to their mtime.
    """
    file_mtimes: Dict[str, float] = {}

    for directory_str in directories:
        directory = Path(directory_str)
        if not directory.exists() or not directory.is_dir():
            continue

        for md_file in directory.rglob("*.md"):
            try:
                file_mtimes[str(md_file)] = md_file.stat().st_mtime
            except OSError:
                continue

    return file_mtimes


def generate_chunk_id(file_path: str, chunk_index: int) -> int:
    """
    Generate a stable signed 63-bit ID for a chunk.

    The ID is derived from the file path (upper 47 bits) and chunk index
    (lower 16 bits), ensuring:
    - Same file + index always produces the same ID
    - Different files produce different ID prefixes
    - Up to 65536 chunks per file
    - Result fits in signed 64-bit integer (required by FAISS/numpy)

    Args:
        file_path: Absolute path to the source file.
        chunk_index: Index of the chunk within the file (0-based).

    Returns:
        A stable signed 64-bit integer ID (always positive).
    """
    # Hash the file path and use upper 47 bits (not 48, to fit in signed int64)
    file_hash = hashlib.sha256(file_path.encode("utf-8")).hexdigest()[:12]
    file_prefix = int(file_hash, 16) & 0x7FFFFFFFFFFF  # Mask to 47 bits

    # Combine with chunk index (lower 16 bits)
    chunk_id = (file_prefix << 16) | (chunk_index & 0xFFFF)

    return chunk_id


def load_single_file(file_path: str) -> Tuple[Path, str]:
    """
    Load a single markdown file.

    Args:
        file_path: Path to the markdown file.

    Returns:
        Tuple of (Path, content).

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If file is not a markdown file.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if path.suffix != ".md":
        raise ValueError(f"Not a markdown file: {file_path}")

    content = path.read_text(encoding="utf-8")
    return path, content
