"""Tests for response formatter module."""

import pytest

from markdown_qa.formatter import ResponseFormatter


class TestResponseFormatter:
    """Test response formatter for formatting answers with source citations."""

    def test_format_response_with_single_source(self):
        """Test formatting response with a single source."""
        formatter = ResponseFormatter()
        answer = "This is the answer."
        sources = ["/path/to/doc.md"]

        result = formatter.format_response(answer, sources)

        assert result["answer"] == answer
        assert len(result["sources"]) == 1
        assert result["sources"][0] == "/path/to/doc.md"

    def test_format_response_with_multiple_sources(self):
        """Test formatting response with multiple sources."""
        formatter = ResponseFormatter()
        answer = "This is the answer."
        sources = ["/path/to/doc1.md", "/path/to/doc2.md"]

        result = formatter.format_response(answer, sources)

        assert result["answer"] == answer
        assert len(result["sources"]) == 2
        assert result["sources"][0] == "/path/to/doc1.md"
        assert result["sources"][1] == "/path/to/doc2.md"

    def test_format_response_deduplicates_sources(self):
        """Test that duplicate sources are deduplicated."""
        formatter = ResponseFormatter()
        answer = "This is the answer."
        sources = [
            "/path/to/doc.md",
            "/path/to/doc.md",
            "/path/to/doc2.md",
        ]

        result = formatter.format_response(answer, sources)

        assert len(result["sources"]) == 2  # Should deduplicate by file path
        assert result["sources"][0] == "/path/to/doc.md"
        assert result["sources"][1] == "/path/to/doc2.md"

    def test_format_for_display(self):
        """Test formatting for human-readable display."""
        formatter = ResponseFormatter()
        answer = "This is the answer."
        sources = ["/path/to/doc.md"]

        result = formatter.format_for_display(answer, sources)

        assert answer in result
        assert "Sources:" in result
        assert "/path/to/doc.md" in result

    def test_format_for_display_multiple_sources(self):
        """Test formatting for display with multiple sources."""
        formatter = ResponseFormatter()
        answer = "This is the answer."
        sources = ["/path/to/doc1.md", "/path/to/doc2.md"]

        result = formatter.format_for_display(answer, sources)

        assert answer in result
        assert "Sources:" in result
        assert "/path/to/doc1.md" in result
        assert "/path/to/doc2.md" in result
        assert "1. /path/to/doc1.md" in result
        assert "2. /path/to/doc2.md" in result

    def test_format_response_with_legacy_dict_format(self):
        """Test that legacy dict format is still supported for backwards compatibility."""
        formatter = ResponseFormatter()
        answer = "This is the answer."
        sources = [
            {"file_path": "/path/to/doc.md", "section": "Introduction", "text": "Some text."},
        ]

        result = formatter.format_response(answer, sources)

        assert result["answer"] == answer
        assert len(result["sources"]) == 1
        assert result["sources"][0] == "/path/to/doc.md"

    def test_format_for_display_with_legacy_dict_format(self):
        """Test display formatting with legacy dict format."""
        formatter = ResponseFormatter()
        answer = "This is the answer."
        sources = [
            {"file_path": "/path/to/doc.md", "section": "Introduction", "text": "Some text."},
        ]

        result = formatter.format_for_display(answer, sources)

        assert answer in result
        assert "Sources:" in result
        assert "/path/to/doc.md" in result
