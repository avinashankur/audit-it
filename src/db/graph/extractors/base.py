"""Base contract for document and entity extraction strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseExtractor(ABC):
    """Abstract base class for graph entity and relationship extractors."""

    @abstractmethod
    def extract(self, data: Any, **kwargs: Any) -> list[Any]:
        """Extract graph entities or causal relationship edges from input data."""
        raise NotImplementedError
