
from typing import Any


class AuditItError(Exception):
    """Base error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# Config
class ConfigurationError(AuditItError):
    pass


# Ingestion
class IngestionError(AuditItError):
    pass


class DocumentLoadError(IngestionError):
    pass


class PDFParseError(IngestionError):
    pass


class ChunkingError(IngestionError):
    pass


class TableExtractionError(IngestionError):
    pass


# Storage & Graph
class StorageError(AuditItError):
    pass


class Neo4jConnectionError(StorageError):
    pass


class GraphIntegrityError(StorageError):
    pass


class VectorStoreError(StorageError):
    pass


# Extraction
class ExtractionError(AuditItError):
    pass


class SchemaValidationError(ExtractionError):
    pass


class RuleExtractionError(ExtractionError):
    pass


# Retrieval
class RetrievalError(AuditItError):
    pass


class GraphTraversalError(RetrievalError):
    pass


class ContextBuildError(RetrievalError):
    pass


# LLM Providers
class LLMProviderError(AuditItError):
    pass


class AuthenticationError(LLMProviderError):
    pass


class RateLimitExceededError(LLMProviderError):
    pass


class ModelResponseError(LLMProviderError):
    pass
