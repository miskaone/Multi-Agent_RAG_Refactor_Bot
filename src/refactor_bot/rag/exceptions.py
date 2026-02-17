"""RAG-specific exceptions."""


class RAGError(Exception):
    """Base exception for RAG operations."""


class EmbeddingError(RAGError):
    """Exception raised when embedding generation fails."""


class VectorStoreError(RAGError):
    """Exception raised when vector store operations fail."""


class RetrievalError(RAGError):
    """Exception raised when retrieval operations fail."""
