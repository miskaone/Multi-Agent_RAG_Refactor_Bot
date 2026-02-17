from unittest.mock import patch

from refactor_bot.models.schemas import RetrievalResult
from refactor_bot.rag.embeddings import EmbeddingService
from refactor_bot.rag.retriever import Retriever
from refactor_bot.rag.vector_store import VectorStore


def test_upsert_and_query(
    chroma_temp_dir,
    mock_openai_client,
    sample_embedding_records
):
    """Verify basic upsert and query operations return RetrievalResult instances."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        embedding_service = EmbeddingService(api_key="test-key")
        vector_store = VectorStore(persist_dir=chroma_temp_dir)

        # Embed records first
        embedded = embedding_service.embed_symbols(sample_embedding_records)
        vector_store.upsert(embedded)

        retriever = Retriever(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

        # Query
        results = retriever.query("async file operations", top_k=3)

        # Verify results are RetrievalResult instances
        assert len(results) > 0
        assert all(isinstance(r, RetrievalResult) for r in results)
        assert all(hasattr(r, "symbol") for r in results)
        assert all(hasattr(r, "file_path") for r in results)
        assert all(hasattr(r, "similarity") for r in results)


def test_query_returns_relevant_results(
    chroma_temp_dir,
    mock_openai_client,
    sample_embedding_records
):
    """Verify that queries return semantically relevant results with high similarity."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        embedding_service = EmbeddingService(api_key="test-key")
        vector_store = VectorStore(persist_dir=chroma_temp_dir)

        # Embed and upsert
        embedded = embedding_service.embed_symbols(sample_embedding_records)
        vector_store.upsert(embedded)

        retriever = Retriever(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

        # Query for file operations - should return fileOps symbols
        results = retriever.query("async file operations", top_k=5)

        assert len(results) > 0
        top_result = results[0]
        assert top_result.similarity >= 0.8


def test_similarity_threshold_filtering(
    chroma_temp_dir,
    mock_openai_client,
    sample_embedding_records
):
    """Verify that similarity threshold filters out low-scoring results."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        embedding_service = EmbeddingService(api_key="test-key")
        vector_store = VectorStore(persist_dir=chroma_temp_dir)

        embedded = embedding_service.embed_symbols(sample_embedding_records)
        vector_store.upsert(embedded)

        retriever = Retriever(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

        # Query with very high threshold
        results_high = retriever.query(
            "async file operations", top_k=10, similarity_threshold=0.99
        )

        # Query with normal threshold
        results_normal = retriever.query(
            "async file operations", top_k=10, similarity_threshold=0.5
        )

        # High threshold should return fewer or equal results
        assert len(results_high) <= len(results_normal)


def test_incremental_reindex_skips_unchanged(
    chroma_temp_dir,
    mock_openai_client,
    sample_repo_index
):
    """Verify that incremental reindexing skips unchanged files."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        embedding_service = EmbeddingService(api_key="test-key")
        vector_store = VectorStore(persist_dir=chroma_temp_dir)
        retriever = Retriever(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

        # First index
        stats1 = retriever.index_repo(sample_repo_index, force=True)
        assert stats1["embedded"] > 0

        # Second index with same data (incremental)
        stats2 = retriever.index_repo(sample_repo_index, force=False)
        assert stats2["embedded"] == 0
        assert stats2["skipped"] == stats1["embedded"]


def test_incremental_reindex_updates_changed(
    chroma_temp_dir,
    mock_openai_client,
    sample_repo_index
):
    """Verify that incremental reindexing updates files with changed hashes."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        embedding_service = EmbeddingService(api_key="test-key")
        vector_store = VectorStore(persist_dir=chroma_temp_dir)
        retriever = Retriever(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

        # First index
        stats1 = retriever.index_repo(sample_repo_index, force=True)
        initial_embedded = stats1["embedded"]

        # Modify a file's hash to simulate a change (pick one with symbols)
        for f in sample_repo_index.files:
            if f.symbols:
                f.hash = "modified_hash_123"
                break

        # Second index (incremental)
        stats2 = retriever.index_repo(sample_repo_index, force=False)
        assert stats2["embedded"] > 0
        assert stats2["skipped"] > 0
        assert stats2["skipped"] < initial_embedded


def test_delete_removed_symbols(
    chroma_temp_dir,
    mock_openai_client,
    sample_repo_index
):
    """Verify that symbols removed from RepoIndex are deleted from the store."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        embedding_service = EmbeddingService(api_key="test-key")
        vector_store = VectorStore(persist_dir=chroma_temp_dir)
        retriever = Retriever(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )

        # First index
        retriever.index_repo(sample_repo_index, force=True)

        # Remove a symbol from the first file that has symbols
        for f in sample_repo_index.files:
            if f.symbols:
                f.symbols = f.symbols[:-1]
                break

        # Reindex (incremental)
        stats2 = retriever.index_repo(sample_repo_index, force=False)
        assert stats2["deleted"] > 0


def test_get_by_file(
    chroma_temp_dir,
    mock_openai_client,
    sample_embedding_records
):
    """Verify that querying by file_path returns only symbols from that file."""
    with patch("openai.OpenAI", return_value=mock_openai_client):
        embedding_service = EmbeddingService(api_key="test-key")
        vector_store = VectorStore(persist_dir=chroma_temp_dir)

        embedded = embedding_service.embed_symbols(sample_embedding_records)
        vector_store.upsert(embedded)

        if sample_embedding_records:
            target_file = sample_embedding_records[0].file_path

            results = vector_store.get_by_file(target_file)

            assert len(results) > 0
            for r in results:
                assert r.get("metadata", {}).get("file_path") == target_file
