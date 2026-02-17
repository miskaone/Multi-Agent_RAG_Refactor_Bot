"""Embedding service using OpenAI API."""

import os
import time
from typing import Optional

import openai

from refactor_bot.models import EmbeddingRecord


class EmbeddingService:
    """Service for generating embeddings using OpenAI API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        batch_size: int = 100,
    ):
        """Initialize the embedding service.

        Args:
            api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
            model: Model to use for embeddings.
            batch_size: Number of texts to embed in a single API call.

        Raises:
            ValueError: If api_key is None and OPENAI_API_KEY env var is not set.
        """
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")
            if api_key is None:
                raise ValueError(
                    "OpenAI API key must be provided or set in OPENAI_API_KEY env var"
                )

        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
        self.batch_size = batch_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors in the same order as input texts.

        Raises:
            openai.RateLimitError: If rate limit is exceeded after retries.
            openai.APIConnectionError: If connection fails after retries.
        """
        all_embeddings: list[list[float]] = []

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            embeddings = self._embed_batch_with_retry(batch)
            all_embeddings.extend(embeddings)

        return all_embeddings

    def _embed_batch_with_retry(self, batch: list[str]) -> list[list[float]]:
        """Embed a batch of texts with retry logic.

        Args:
            batch: List of text strings to embed.

        Returns:
            List of embedding vectors.

        Raises:
            openai.RateLimitError: If rate limit is exceeded after retries.
            openai.APIConnectionError: If connection fails after retries.
        """
        max_retries = 3
        retry_delays = [1, 2, 4]  # Exponential backoff in seconds

        for attempt in range(max_retries):
            try:
                response = self.client.embeddings.create(input=batch, model=self.model)
                return [item.embedding for item in response.data]
            except (openai.RateLimitError, openai.APIConnectionError):
                if attempt < max_retries - 1:
                    time.sleep(retry_delays[attempt])
                else:
                    raise

        raise RuntimeError("Unreachable: retry loop exited without return or raise")

    def embed_symbols(self, records: list[EmbeddingRecord]) -> list[EmbeddingRecord]:
        """Generate embeddings for a list of embedding records.

        Mutates the input records in-place by setting their embedding_vector field.

        Args:
            records: List of EmbeddingRecord instances.

        Returns:
            The same list of EmbeddingRecord instances with embedding_vector set.

        Raises:
            openai.RateLimitError: If rate limit is exceeded after retries.
            openai.APIConnectionError: If connection fails after retries.
        """
        # Extract source code from each record
        texts = [record.source_code for record in records]

        # Generate embeddings
        embeddings = self.embed_texts(texts)

        # Set embedding_vector on each record
        for record, embedding in zip(records, embeddings):
            record.embedding_vector = embedding

        return records
