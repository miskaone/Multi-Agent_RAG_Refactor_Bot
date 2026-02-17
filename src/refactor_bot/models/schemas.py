"""Pydantic data models for the refactor bot."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReactMetadata(BaseModel):
    """React-specific file/symbol metadata."""

    model_config = ConfigDict(frozen=False)

    is_component: bool = False
    is_server_component: Optional[bool] = None
    uses_hooks: list[str] = Field(default_factory=list)
    has_suspense_boundary: bool = False
    is_barrel_file: bool = False


class SymbolInfo(BaseModel):
    """A single extracted symbol (function, class, method, arrow function)."""

    model_config = ConfigDict(frozen=False)

    name: str
    type: str  # one of "function", "class", "method", "arrow_function"
    file_path: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    source_code: str
    is_component: bool = False
    is_server_component: Optional[bool] = None
    uses_hooks: list[str] = Field(default_factory=list)
    has_suspense_boundary: bool = False
    imports: list[str] = Field(default_factory=list)
    calls: list[str] = Field(default_factory=list)


class FileInfo(BaseModel):
    """A single source file."""

    model_config = ConfigDict(frozen=False)

    file_path: str
    relative_path: str
    language: str  # "javascript", "typescript", "tsx", "jsx"
    symbols: list[SymbolInfo] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)  # raw import source strings
    exports: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)  # resolved file paths
    hash: str  # SHA256 of file content
    react_metadata: Optional[ReactMetadata] = None
    errors: list[str] = Field(default_factory=list)  # parsing errors for this file


class RepoIndex(BaseModel):
    """Complete repository index."""

    model_config = ConfigDict(frozen=False)

    repo_path: str
    files: list[FileInfo] = Field(default_factory=list)
    dependency_graph: dict[str, list[str]] = Field(default_factory=dict)
    is_react_project: bool = False
    project_type: Optional[str] = None  # "react", "nextjs", or None
    package_json_path: Optional[str] = None
    total_files: int = 0
    total_symbols: int = 0
    indexed_at: datetime = Field(default_factory=datetime.now)


class EmbeddingRecord(BaseModel):
    """Embedding vector with metadata (vector populated in Cycle 2)."""

    model_config = ConfigDict(frozen=False)

    id: str  # "{file_path}::{symbol_name}"
    file_path: str
    symbol: str
    type: str  # "function", "class", "file"
    source_code: str
    hash: str
    dependencies: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    embedding_vector: Optional[list[float]] = None
    react_metadata: Optional[ReactMetadata] = None


class RetrievalResult(BaseModel):
    """Result from vector store retrieval."""

    model_config = ConfigDict(frozen=False)

    id: str
    file_path: str
    symbol: str
    type: str
    source_code: str
    distance: float
    similarity: float
    metadata: dict[str, Any] = Field(default_factory=dict)
