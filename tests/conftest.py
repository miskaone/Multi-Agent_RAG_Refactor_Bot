import math
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from refactor_bot.agents.repo_indexer import RepoIndexer
from refactor_bot.models.schemas import EmbeddingRecord


@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def embedding_repo_path(fixtures_dir):
    return str((fixtures_dir / "embedding_repo").resolve())


@pytest.fixture
def sample_repo_index(embedding_repo_path):
    indexer = RepoIndexer()
    return indexer.index(embedding_repo_path)


@pytest.fixture
def sample_embedding_records(sample_repo_index):
    records = []
    for file_info in sample_repo_index.files:
        for symbol in file_info.symbols:
            records.append(EmbeddingRecord(
                id=f"{file_info.file_path}::{symbol.name}",
                file_path=file_info.file_path,
                symbol=symbol.name,
                type=symbol.type,
                source_code=symbol.source_code,
                hash=file_info.hash,
                dependencies=file_info.dependencies,
                imports=file_info.imports,
            ))
    return records


def _make_vector(base_value: float, dim: int = 1536) -> list[float]:
    """Create a normalized vector with a distinctive pattern."""
    vec = [base_value + (i % 10) * 0.01 for i in range(dim)]
    magnitude = math.sqrt(sum(x * x for x in vec))
    return [x / magnitude for x in vec]


# Engineered vectors for deterministic similarity tests
FILE_OPS_VECTOR = _make_vector(0.8)
STRING_HELPER_VECTOR = _make_vector(0.2)
DATA_LOADER_VECTOR = _make_vector(0.5)
QUERY_FILE_OPS_VECTOR = _make_vector(0.81)  # Very close to FILE_OPS_VECTOR


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client that returns engineered vectors based on input text."""
    def create_embeddings(**kwargs):
        texts = kwargs.get("input", [])

        embeddings = []
        for i, text in enumerate(texts):
            text_lower = text.lower()
            if any(kw in text_lower for kw in ["file", "read", "write", "delete", "async"]):
                vec = FILE_OPS_VECTOR
            elif any(kw in text_lower for kw in ["capitalize", "slug", "camel", "string"]):
                vec = STRING_HELPER_VECTOR
            elif any(kw in text_lower for kw in ["data", "loader", "fetch", "component"]):
                vec = DATA_LOADER_VECTOR
            else:
                vec = _make_vector(0.5)

            embedding_obj = MagicMock()
            embedding_obj.embedding = vec
            embedding_obj.index = i
            embeddings.append(embedding_obj)

        response = MagicMock()
        response.data = embeddings
        return response

    mock_client = MagicMock()
    mock_client.embeddings.create = MagicMock(side_effect=create_embeddings)
    return mock_client


@pytest.fixture
def chroma_temp_dir(tmp_path):
    return str(tmp_path / "chroma_test")
