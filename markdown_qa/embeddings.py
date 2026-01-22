"""Embedding generation module using OpenAI-compatible API with retry logic and caching."""

import hashlib
import json
import time
from pathlib import Path
from typing import List, Optional

from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from markdown_qa.config import APIConfig
from markdown_qa.logger import get_server_logger


class EmbeddingGenerator:
    """Generates embeddings using OpenAI-compatible API with retry logic and caching."""

    def __init__(
        self,
        api_config: Optional[APIConfig] = None,
        cache_dir: Optional[Path] = None,
        embedding_model: Optional[str] = None,
    ):
        """
        Initialize the embedding generator.

        Args:
            api_config: API configuration. If None, will create from defaults.
            cache_dir: Directory for caching embeddings. If None, uses default cache.
            embedding_model: Embedding model name. If None, uses model from api_config or default.
        """
        if api_config is None:
            api_config = APIConfig()

        self.api_config = api_config
        self.client = OpenAI(
            base_url=api_config.base_url,
            api_key=api_config.api_key,
        )
        # Use provided model, or from api_config, or default
        self.embedding_model = embedding_model or api_config.embedding_model or "text-embedding-3-small"

        # Set up cache directory
        if cache_dir is None:
            cache_dir = Path.home() / ".markdown-qa" / "cache" / "embeddings"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_server_logger()

    def _get_cache_key(self, text: str) -> str:
        """Generate a cache key for a text string."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the cache file path for a cache key."""
        return self.cache_dir / f"{cache_key}.json"

    def _load_from_cache(self, cache_key: str) -> Optional[List[float]]:
        """Load embedding from cache if it exists."""
        cache_path = self._get_cache_path(cache_key)
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    data = json.load(f)
                    embedding = data.get("embedding")
                    if isinstance(embedding, list) and all(isinstance(x, (int, float)) for x in embedding):
                        return [float(x) for x in embedding]
            except Exception:
                # If cache file is corrupted, ignore it
                return None
        return None

    def _save_to_cache(self, cache_key: str, embedding: List[float], text: str) -> None:
        """Save embedding to cache."""
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, "w") as f:
                json.dump({"embedding": embedding, "text": text[:100]}, f)
        except Exception:
            # If cache write fails, continue without caching
            pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _generate_embedding_with_retry(self, text: str) -> List[float]:
        """
        Generate embedding with retry logic and exponential backoff.

        Args:
            text: Text to generate embedding for.

        Returns:
            List of floats representing the embedding vector.
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            # Log the error and re-raise for retry logic
            raise Exception(f"Failed to generate embedding: {e}") from e

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text, using cache if available.

        Args:
            text: Text to generate embedding for.

        Returns:
            List of floats representing the embedding vector.
        """
        cache_key = self._get_cache_key(text)

        # Try to load from cache first
        cached_embedding = self._load_from_cache(cache_key)
        if cached_embedding is not None:
            return cached_embedding

        # Generate new embedding with retry logic
        embedding = self._generate_embedding_with_retry(text)

        # Save to cache
        self._save_to_cache(cache_key, embedding, text)

        return embedding

    def generate_embeddings(
        self, texts: List[str], show_progress: bool = False
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to generate embeddings for.
            show_progress: Whether to show progress indicators.

        Returns:
            List of embedding vectors.
        """
        embeddings = []
        total = len(texts)
        start_time = time.time()

        for i, text in enumerate(texts):
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)

            # Show progress if requested and enough time has passed
            if show_progress and total > 10:
                elapsed = time.time() - start_time
                if elapsed > 2.0 or i == total - 1:  # Show if > 2s or at end
                    progress = (i + 1) / total * 100
                    self.logger.info(f"Generating embeddings: {i+1}/{total} ({progress:.1f}%)")

        return embeddings
