"""Vector store using ChromaDB."""

import json
import os
from typing import Any, Optional, cast

import chromadb

from refactor_bot.models import EmbeddingRecord


def _validate_file_path(file_path: str) -> None:
    """Validate that a file path doesn't contain traversal sequences."""
    if ".." in file_path.split(os.sep):
        raise ValueError(f"Invalid file_path: path traversal detected in '{file_path}'")


def _deserialize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Deserialize JSON-encoded metadata fields."""
    result = dict(metadata)
    for field in ("dependencies", "imports"):
        if field in result and isinstance(result[field], str):
            result[field] = json.loads(result[field])
    return result


class VectorStore:
    """Vector store for managing code embeddings using ChromaDB."""

    def __init__(
        self,
        persist_dir: str = "./data/embeddings",
        collection_name: str = "symbols",
    ):
        """Initialize the vector store.

        Args:
            persist_dir: Directory to persist the ChromaDB data.
            collection_name: Name of the collection to use.
        """
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, records: list[EmbeddingRecord]) -> None:
        """Insert or update embedding records in the vector store.

        Args:
            records: List of EmbeddingRecord instances to upsert.

        Raises:
            ValueError: If any record has an invalid file_path.
        """
        valid_records = [r for r in records if r.embedding_vector is not None]

        if not valid_records:
            return

        for r in valid_records:
            _validate_file_path(r.file_path)

        ids = [r.id for r in valid_records]
        embeddings = cast(list[list[float]], [r.embedding_vector for r in valid_records])
        documents = [r.source_code for r in valid_records]
        metadatas: list[dict[str, Any]] = [
            {
                "file_path": r.file_path,
                "symbol": r.symbol,
                "type": r.type,
                "hash": r.hash,
                "dependencies": json.dumps(r.dependencies),
                "imports": json.dumps(r.imports),
            }
            for r in valid_records
        ]

        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,  # type: ignore[arg-type]
            documents=documents,
            metadatas=metadatas,  # type: ignore[arg-type]
        )

    def delete(self, ids: list[str]) -> None:
        """Delete records by their IDs.

        Args:
            ids: List of record IDs to delete.
        """
        if ids:
            self.collection.delete(ids=ids)

    def get_by_file(self, file_path: str) -> list[dict[str, Any]]:
        """Get all records for a specific file.

        Args:
            file_path: Path to the file.

        Returns:
            List of records as dictionaries with deserialized metadata.

        Raises:
            ValueError: If file_path contains traversal sequences.
        """
        _validate_file_path(file_path)
        results = self.collection.get(where={"file_path": file_path})

        records: list[dict[str, Any]] = []
        if results["ids"]:
            ids = results["ids"]
            docs = results["documents"] or [None] * len(ids)
            metas = results["metadatas"] or [{}] * len(ids)  # type: ignore[assignment]
            embeds = results["embeddings"] or [None] * len(ids)

            for i in range(len(ids)):
                metadata = _deserialize_metadata(metas[i])  # type: ignore[arg-type]
                records.append({
                    "id": ids[i],
                    "document": docs[i],
                    "metadata": metadata,
                    "embedding": embeds[i],
                })

        return records

    def query_by_embedding(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Query the vector store by embedding vector.

        Args:
            query_embedding: Embedding vector to search for.
            top_k: Number of results to return.
            where: Optional filter criteria.

        Returns:
            List of query results as dictionaries with deserialized metadata.
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],  # type: ignore[arg-type]
            n_results=top_k,
            where=where,
        )

        records: list[dict[str, Any]] = []
        result_ids = results["ids"]
        if result_ids and result_ids[0]:
            row_ids = result_ids[0]
            row_docs = results["documents"][0] if results["documents"] else [None] * len(row_ids)  # type: ignore[index]
            row_metas = results["metadatas"][0] if results["metadatas"] else [{}] * len(row_ids)  # type: ignore[index]
            row_dists = results["distances"][0] if results["distances"] else [0.0] * len(row_ids)  # type: ignore[index]

            for i in range(len(row_ids)):
                metadata = _deserialize_metadata(row_metas[i])  # type: ignore[arg-type]
                records.append({
                    "id": row_ids[i],
                    "document": row_docs[i],
                    "metadata": metadata,
                    "distance": row_dists[i],
                })

        return records

    def get_all_hashes(self) -> dict[str, str]:
        """Get all record IDs and their hashes.

        Returns:
            Dictionary mapping record ID to hash.
        """
        results = self.collection.get()

        hashes: dict[str, str] = {}
        if results["ids"]:
            metas = results["metadatas"] or [{}] * len(results["ids"])  # type: ignore[assignment]
            for i in range(len(results["ids"])):
                record_id = results["ids"][i]
                metadata = metas[i]
                hash_value = metadata.get("hash", "")  # type: ignore[union-attr]
                if isinstance(hash_value, str):
                    hashes[record_id] = hash_value

        return hashes
