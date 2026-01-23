"""Embedding generation module using OpenAI-compatible API with retry logic and caching."""

import hashlib
import json
import time
from pathlib import Path
from typing import List, Optional, Tuple

from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from markdown_qa.config import APIConfig
from markdown_qa.logger import get_server_logger

# Maximum number of texts to send in a single batch API call
# Some APIs (e.g., Alibaba) only support batch sizes up to 10
DEFAULT_BATCH_SIZE = 10


class EmbeddingGenerator:
    """Generates embeddings using OpenAI-compatible API with retry logic and caching."""

    def __init__(
        self,
        api_config: Optional[APIConfig] = None,
        cache_dir: Optional[Path] = None,
        embedding_model: Optional[str] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        """
        Initialize the embedding generator.

        Args:
            api_config: API configuration. If None, will create from defaults.
            cache_dir: Directory for caching embeddings. If None, uses default cache.
            embedding_model: Embedding model name. If None, uses model from api_config or default.
            batch_size: Maximum number of texts to send in a single batch API call.
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
        self.batch_size = batch_size

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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _generate_embeddings_batch_with_retry(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a single batch API call.

        Args:
            texts: List of texts to generate embeddings for.

        Returns:
            List of embedding vectors in the same order as input texts.
        """
        if not texts:
            return []

        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=texts,
            )
            # OpenAI returns embeddings with an index field that indicates
            # the position in the input list. Sort by index to ensure correct order.
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]
        except Exception as e:
            raise Exception(f"Failed to generate batch embeddings: {e}") from e

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

    def _check_cache_for_texts(
        self, texts: List[str]
    ) -> Tuple[List[Tuple[int, List[float]]], List[Tuple[int, str, str]]]:
        """
        Check cache for all texts and separate hits from misses.

        Args:
            texts: List of texts to check cache for.

        Returns:
            Tuple of (cache_hits, cache_misses) where:
                - cache_hits: List of (index, embedding) tuples for cached embeddings
                - cache_misses: List of (index, text, cache_key) tuples for texts needing generation
        """
        cache_hits: List[Tuple[int, List[float]]] = []
        cache_misses: List[Tuple[int, str, str]] = []

        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached_embedding = self._load_from_cache(cache_key)
            if cached_embedding is not None:
                cache_hits.append((i, cached_embedding))
            else:
                cache_misses.append((i, text, cache_key))

        return cache_hits, cache_misses

    def generate_embeddings(
        self, texts: List[str], show_progress: bool = False
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts using batch API calls.

        This method uses a hybrid approach:
        1. Check cache for all texts first
        2. Generate embeddings for cache misses in batches
        3. Save new embeddings to cache
        4. Return all embeddings in original order

        Args:
            texts: List of texts to generate embeddings for.
            show_progress: Whether to show progress indicators.

        Returns:
            List of embedding vectors in the same order as input texts.
        """
        if not texts:
            return []

        total = len(texts)
        start_time = time.time()

        # Step 1: Check cache for all texts
        cache_hits, cache_misses = self._check_cache_for_texts(texts)

        if show_progress and cache_hits:
            self.logger.info(
                f"Found {len(cache_hits)}/{total} embeddings in cache, "
                f"generating {len(cache_misses)} new embeddings"
            )

        # Prepare result array with placeholders
        embeddings: List[Optional[List[float]]] = [None] * total

        # Fill in cached embeddings
        for idx, embedding in cache_hits:
            embeddings[idx] = embedding

        # Step 2: Generate embeddings for cache misses in batches
        if cache_misses:
            # Extract texts for batch processing
            miss_indices = [item[0] for item in cache_misses]
            miss_texts = [item[1] for item in cache_misses]
            miss_cache_keys = [item[2] for item in cache_misses]

            # Process in batches
            num_batches = (len(miss_texts) + self.batch_size - 1) // self.batch_size
            generated_count = 0

            for batch_idx in range(num_batches):
                batch_start = batch_idx * self.batch_size
                batch_end = min(batch_start + self.batch_size, len(miss_texts))

                batch_texts = miss_texts[batch_start:batch_end]
                batch_indices = miss_indices[batch_start:batch_end]
                batch_cache_keys = miss_cache_keys[batch_start:batch_end]

                # Generate batch embeddings
                batch_embeddings = self._generate_embeddings_batch_with_retry(batch_texts)

                # Step 3: Save to cache and fill in results
                for i, (idx, embedding, cache_key, text) in enumerate(
                    zip(batch_indices, batch_embeddings, batch_cache_keys, batch_texts)
                ):
                    self._save_to_cache(cache_key, embedding, text)
                    embeddings[idx] = embedding
                    generated_count += 1

                # Show progress if requested
                if show_progress and len(cache_misses) > 10:
                    elapsed = time.time() - start_time
                    if elapsed > 2.0 or generated_count == len(cache_misses):
                        progress = generated_count / len(cache_misses) * 100
                        self.logger.info(
                            f"Generating embeddings: {generated_count}/{len(cache_misses)} "
                            f"({progress:.1f}%) [batch {batch_idx + 1}/{num_batches}]"
                        )

        # All embeddings should be filled in now
        return embeddings  # type: ignore[return-value]
