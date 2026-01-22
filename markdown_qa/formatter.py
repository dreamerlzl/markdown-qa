"""Response formatter module for formatting answers with source citations."""

from typing import Any, Dict, List, Union


class ResponseFormatter:
    """Formats Q&A responses with source citations."""

    def format_response(
        self, answer: str, sources: List[Union[str, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Format answer with source citations.

        Args:
            answer: The generated answer text.
            sources: List of file path strings.

        Returns:
            Dictionary with 'answer' and 'sources' keys.
        """
        # Extract file paths and deduplicate
        unique_paths = self._deduplicate_sources(sources)

        return {
            "answer": answer,
            "sources": unique_paths,
        }

    def format_for_display(
        self, answer: str, sources: List[Union[str, Dict[str, Any]]]
    ) -> str:
        """
        Format answer and sources as a human-readable string.

        Args:
            answer: The generated answer text.
            sources: List of file path strings.

        Returns:
            Formatted string ready for display.
        """
        formatted = f"{answer}\n\n"
        if sources:
            formatted += self.format_sources(sources)
        return formatted

    def format_sources(self, sources: List[Union[str, Dict[str, Any]]]) -> str:
        """
        Format sources as a human-readable string.

        Args:
            sources: List of file path strings.

        Returns:
            Formatted string with numbered sources.
        """
        if not sources:
            return ""
        formatted = "Sources:\n"
        unique_paths = self._deduplicate_sources(sources)
        for i, file_path in enumerate(unique_paths, 1):
            formatted += f"{i}. {file_path}\n"
        return formatted

    def _deduplicate_sources(
        self, sources: List[Union[str, Dict[str, Any]]]
    ) -> List[str]:
        """
        Deduplicate sources by file path.

        Args:
            sources: List of file path strings or dictionaries with file_path key.

        Returns:
            Deduplicated list of file paths.
        """
        seen = set()
        unique = []
        for source in sources:
            # Handle both string paths and legacy dict format
            if isinstance(source, str):
                file_path = source
            else:
                file_path = source.get("file_path", "")
            if file_path and file_path not in seen:
                seen.add(file_path)
                unique.append(file_path)
        return unique
