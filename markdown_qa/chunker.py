"""Text chunking module using LangChain's MarkdownTextSplitter with metadata preservation."""

from pathlib import Path
from typing import Any, Dict, List, Tuple

from langchain_text_splitters import MarkdownTextSplitter


class MarkdownChunker:
    """Chunks markdown content while preserving structural metadata."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialize the markdown chunker.

        Args:
            chunk_size: Maximum size of each chunk in characters (default: 1000).
            chunk_overlap: Overlap between adjacent chunks in characters (default: 200).
        """
        self.splitter = MarkdownTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk_file(
        self, file_path: Path, content: str
    ) -> List[Dict[str, Any]]:
        """
        Chunk a markdown file while preserving metadata.

        Args:
            file_path: Path to the markdown file.
            content: Content of the markdown file.

        Returns:
            List of dictionaries, each containing:
            - 'text': The chunk text content
            - 'metadata': Dictionary with 'file_path' and 'section' information
        """
        # Split the markdown content
        chunks = self.splitter.create_documents([content])

        # Extract metadata from chunks and add file path
        result = []
        for chunk in chunks:
            metadata = chunk.metadata.copy()
            metadata["file_path"] = str(file_path)

            # Extract section information from metadata if available
            # LangChain's MarkdownTextSplitter may include section headers in metadata
            if "section" not in metadata:
                # Try to extract section from chunk content or metadata
                # This is a fallback - LangChain may already provide this
                metadata["section"] = self._extract_section_from_chunk(chunk.page_content)

            result.append(
                {
                    "text": chunk.page_content,
                    "metadata": metadata,
                }
            )

        return result

    def _extract_section_from_chunk(self, chunk_text: str) -> str:
        """
        Extract section header from chunk text if available.

        Args:
            chunk_text: The chunk text content.

        Returns:
            Section header string or empty string if not found.
        """
        lines = chunk_text.split("\n")
        for line in lines[:5]:  # Check first few lines for headers
            line = line.strip()
            if line.startswith("#"):
                # Remove markdown header markers
                return line.lstrip("#").strip()
        return ""

    def chunk_files(
        self, files: List[Tuple[Path, str]]
    ) -> List[Dict[str, Any]]:
        """
        Chunk multiple markdown files.

        Args:
            files: List of tuples containing (file_path, content).

        Returns:
            List of all chunks from all files with metadata.
        """
        all_chunks = []
        for file_path, content in files:
            chunks = self.chunk_file(file_path, content)
            all_chunks.extend(chunks)
        return all_chunks
