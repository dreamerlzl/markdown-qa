"""WebSocket message protocol definitions."""

from typing import Any, Dict, List, Literal, Optional


class MessageType:
    """Message type constants."""

    QUERY = "query"
    RESPONSE = "response"
    ERROR = "error"
    STATUS = "status"
    STREAM_START = "stream_start"
    STREAM_CHUNK = "stream_chunk"
    STREAM_END = "stream_end"


def _deduplicate_paths(paths: List[str]) -> List[str]:
    """Return first-seen unique paths while preserving order."""
    seen: set[str] = set()
    unique_paths: List[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            unique_paths.append(path)
    return unique_paths


def create_query_message(question: str, index: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a query message.

    Args:
        question: The question to ask.
        index: Optional index name to query.

    Returns:
        Query message dictionary.
    """
    msg: Dict[str, Any] = {"type": MessageType.QUERY, "question": question}
    if index:
        msg["index"] = index
    return msg


def create_response_message(
    answer: str, sources: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create a response message.

    Args:
        answer: The generated answer.
        sources: List of source dictionaries.

    Returns:
        Response message dictionary.
    """
    return {
        "type": MessageType.RESPONSE,
        "answer": answer,
        "sources": sources,
    }


def create_error_message(message: str) -> Dict[str, Any]:
    """
    Create an error message.

    Args:
        message: Error message text.

    Returns:
        Error message dictionary.
    """
    return {
        "type": MessageType.ERROR,
        "message": message,
    }


def create_status_message(
    status: Literal["ready", "indexing", "not_ready"], message: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a status message.

    Args:
        status: Status value ("ready", "indexing", or "not_ready").
        message: Optional status message text.

    Returns:
        Status message dictionary.
    """
    msg: Dict[str, Any] = {"type": MessageType.STATUS, "status": status}
    if message:
        msg["message"] = message
    return msg


def create_stream_start_message() -> Dict[str, Any]:
    """
    Create a stream start message.

    Returns:
        Stream start message dictionary.
    """
    return {"type": MessageType.STREAM_START}


def create_stream_chunk_message(chunk: str) -> Dict[str, Any]:
    """
    Create a stream chunk message.

    Args:
        chunk: Text chunk of the answer.

    Returns:
        Stream chunk message dictionary.
    """
    return {"type": MessageType.STREAM_CHUNK, "chunk": chunk}


def create_stream_end_message(sources: List[str]) -> Dict[str, Any]:
    """
    Create a stream end message.

    Args:
        sources: List of source file paths.

    Returns:
        Stream end message dictionary.
    """
    return {
        "type": MessageType.STREAM_END,
        "sources": _deduplicate_paths(sources),
    }


def validate_query_message(message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate a query message.

    Args:
        message: Message dictionary to validate.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not isinstance(message, dict):
        return False, "Message must be a dictionary"

    if message.get("type") != MessageType.QUERY:
        return False, f"Invalid message type: {message.get('type')}"

    if "question" not in message:
        return False, "Missing 'question' field"

    if not isinstance(message["question"], str):
        return False, "Field 'question' must be a string"

    if not message["question"].strip():
        return False, "Field 'question' cannot be empty"

    return True, None
