from unittest.mock import MagicMock, patch

import openai
import pytest

from refactor_bot.models.schemas import EmbeddingRecord
from refactor_bot.rag.embeddings import EmbeddingService


def test_embed_texts_returns_correct_dimensions(mock_openai_client):
    """Verify that embedded vectors have 1536 dimensions."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        service = EmbeddingService(api_key="test-key")
        texts = ["function test() {}", "class MyClass {}"]

        vectors = service.embed_texts(texts)

        assert len(vectors) == 2
        assert all(len(vec) == 1536 for vec in vectors)


def test_embed_texts_batching(mock_openai_client):
    """Verify that large batches are split into multiple API calls."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        service = EmbeddingService(api_key="test-key", batch_size=100)

        # Create 250 texts to trigger 3 batches (100 + 100 + 50)
        texts = [f"function test{i}() {{}}" for i in range(250)]

        vectors = service.embed_texts(texts)

        # Verify we got all vectors back
        assert len(vectors) == 250

        # Verify the client was called 3 times (250 / 100 = 3 batches)
        assert mock_openai_client.embeddings.create.call_count == 3


def test_embed_texts_retry_on_rate_limit(mock_openai_client):
    """Verify that rate limit errors trigger retry logic."""
    call_count = 0

    def create_with_rate_limit(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call raises rate limit error
            raise openai.RateLimitError(
                message="Rate limit exceeded",
                response=MagicMock(status_code=429),
                body=None
            )
        else:
            # Second call succeeds
            texts = kwargs.get("input", [])
            embeddings = []
            for i, text in enumerate(texts):
                embedding_obj = MagicMock()
                embedding_obj.embedding = [0.1] * 1536
                embedding_obj.index = i
                embeddings.append(embedding_obj)
            response = MagicMock()
            response.data = embeddings
            return response

    mock_client = MagicMock()
    mock_client.embeddings.create = MagicMock(side_effect=create_with_rate_limit)

    with patch("openai.OpenAI", return_value=mock_client):
        with patch("time.sleep"):  # Mock sleep to avoid waiting
            service = EmbeddingService(api_key="test-key")
            texts = ["function test() {}"]

            vectors = service.embed_texts(texts)

            # Verify we got the result after retry
            assert len(vectors) == 1
            assert len(vectors[0]) == 1536

            # Verify it was called twice (once failed, once succeeded)
            assert mock_client.embeddings.create.call_count == 2


def test_embed_symbols_populates_vectors(mock_openai_client):
    """Verify that embed_symbols sets the embedding_vector field."""
    records = [
        EmbeddingRecord(
            id="test.ts::readFileAsync",
            file_path="test.ts",
            symbol="readFileAsync",
            type="function",
            source_code="async function readFileAsync(path) { return 'data'; }",
            hash="abc123",
        ),
        EmbeddingRecord(
            id="test.ts::writeFileAsync",
            file_path="test.ts",
            symbol="writeFileAsync",
            type="function",
            source_code="async function writeFileAsync(path, data) { }",
            hash="def456",
        ),
    ]

    with patch("openai.OpenAI", return_value=mock_openai_client):
        service = EmbeddingService(api_key="test-key")

        # Before embedding, vectors should be None
        assert all(r.embedding_vector is None for r in records)

        result = service.embed_symbols(records)

        # After embedding, all records should have vectors
        assert all(r.embedding_vector is not None for r in result)
        assert all(len(r.embedding_vector) == 1536 for r in result)


def test_missing_api_key_raises():
    """Verify that missing API key raises ValueError."""
    with patch.dict("os.environ", {}, clear=True):
        # Remove any OPENAI_API_KEY from environment
        with pytest.raises(ValueError, match="API key"):
            EmbeddingService()


def test_embed_texts_empty_input(mock_openai_client):
    """Verify that embedding an empty list returns an empty list."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        service = EmbeddingService(api_key="test-key")

        vectors = service.embed_texts([])

        assert vectors == []
        # Should not call the API for empty input
        assert mock_openai_client.embeddings.create.call_count == 0
