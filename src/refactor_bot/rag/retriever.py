"""Retriever for querying code symbols."""

from refactor_bot.models import EmbeddingRecord, RepoIndex, RetrievalResult
from refactor_bot.rag.exceptions import EmbeddingError, VectorStoreError

from .embeddings import EmbeddingService
from .vector_store import VectorStore

MAX_QUERY_LENGTH = 8000
MAX_TOP_K = 1000


class Retriever:
    """Retriever for querying and indexing code symbols."""

    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore):
        """Initialize the retriever.

        Args:
            embedding_service: Service for generating embeddings.
            vector_store: Vector store for managing embeddings.
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def query(
        self,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.7,
    ) -> list[RetrievalResult]:
        """Query for relevant code symbols.

        Args:
            query: Query string to search for.
            top_k: Number of results to return.
            similarity_threshold: Minimum similarity score (0-1) to include.

        Returns:
            List of RetrievalResult objects sorted by similarity (descending).
        """
        # Validate inputs
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")
        if len(query) > MAX_QUERY_LENGTH:
            raise ValueError(f"Query exceeds maximum length of {MAX_QUERY_LENGTH}")
        if not 1 <= top_k <= MAX_TOP_K:
            raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0.0 and 1.0")

        try:
            query_embedding = self.embedding_service.embed_texts([query])[0]
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

        try:
            raw_results = self.vector_store.query_by_embedding(
                query_embedding=query_embedding,
                top_k=top_k,
            )
        except Exception as e:
            raise VectorStoreError(f"Failed to query vector store: {e}") from e

        # Convert to RetrievalResult objects
        results = []
        for raw in raw_results:
            # Calculate similarity from distance (cosine distance)
            distance = raw.get("distance", 0.0)
            similarity = 1.0 - distance

            # Skip results below threshold
            if similarity < similarity_threshold:
                continue

            metadata = raw.get("metadata", {})
            result = RetrievalResult(
                id=raw["id"],
                file_path=metadata.get("file_path", ""),
                symbol=metadata.get("symbol", ""),
                type=metadata.get("type", ""),
                source_code=raw.get("document", ""),
                distance=distance,
                similarity=similarity,
                metadata=metadata,
            )
            results.append(result)

        # Sort by similarity (descending)
        results.sort(key=lambda r: r.similarity, reverse=True)

        return results

    def index_repo(self, repo_index: RepoIndex, force: bool = False) -> dict[str, int]:
        """Index a repository's symbols into the vector store.

        Args:
            repo_index: Repository index containing file and symbol information.
            force: If True, re-embed all symbols. If False, only embed changed symbols.

        Returns:
            Statistics dictionary with keys: total, embedded, skipped, deleted.
        """
        # Build list of EmbeddingRecord from repo_index
        all_records: list[EmbeddingRecord] = []
        for file_info in repo_index.files:
            for symbol_info in file_info.symbols:
                record_id = f"{file_info.file_path}::{symbol_info.name}"
                record = EmbeddingRecord(
                    id=record_id,
                    file_path=file_info.file_path,
                    symbol=symbol_info.name,
                    type=symbol_info.type,
                    source_code=symbol_info.source_code,
                    hash=file_info.hash,
                    dependencies=file_info.dependencies,
                    imports=file_info.imports,
                )
                all_records.append(record)

        total = len(all_records)
        embedded = 0
        skipped = 0
        deleted = 0

        if force:
            # Re-embed all records
            embedded_records = self.embedding_service.embed_symbols(all_records)
            self.vector_store.upsert(embedded_records)
            embedded = len(embedded_records)
        else:
            # Get existing hashes
            existing_hashes = self.vector_store.get_all_hashes()

            # Determine which records need embedding
            records_to_embed: list[EmbeddingRecord] = []
            current_ids = set()

            for record in all_records:
                current_ids.add(record.id)
                existing_hash = existing_hashes.get(record.id)

                # Embed if new or hash changed
                if existing_hash != record.hash:
                    records_to_embed.append(record)

            # Embed changed/new records
            if records_to_embed:
                embedded_records = self.embedding_service.embed_symbols(records_to_embed)
                self.vector_store.upsert(embedded_records)
                embedded = len(embedded_records)

            skipped = total - embedded

            # Delete removed records
            existing_ids = set(existing_hashes.keys())
            ids_to_delete = list(existing_ids - current_ids)
            if ids_to_delete:
                self.vector_store.delete(ids_to_delete)
                deleted = len(ids_to_delete)

        return {
            "total": total,
            "embedded": embedded,
            "skipped": skipped,
            "deleted": deleted,
        }
