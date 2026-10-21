"""Base abstract storage port for knowledge graph backends."""

from abc import ABC, abstractmethod
from typing import Any


class GraphBackend(ABC):
    """Abstract storage port defining the primitive contract for graph backends."""

    @abstractmethod
    def upsert_node(self, node_id: str, label: str, properties: dict[str, Any]) -> None:
        """Insert or update a node with the given label and properties."""
        pass

    @abstractmethod
    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: dict[str, Any],
    ) -> None:
        """Insert or update a directed relationship edge between two nodes."""
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve node attributes by node_id."""
        pass

    @abstractmethod
    def get_neighbors(
        self,
        node_id: str,
        direction: str = "downstream",
    ) -> list[dict[str, Any]]:
        """Retrieve immediate neighbor nodes and connecting relationships."""
        pass

    @abstractmethod
    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 3,
    ) -> list[dict[str, Any]]:
        """Find all directed paths between source and target up to max_depth."""
        pass

    @abstractmethod
    def get_subgraph(
        self,
        root_id: str | None = None,
        hops: int = 2,
    ) -> dict[str, Any]:
        """Return nodes and edges within `hops` distance from `root_id` (or all if root_id is None)."""
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, int]:
        """Return counts of total nodes, metric nodes, disclosure nodes, and causal edges."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all nodes and edges from storage."""
        pass


# Backwards compatibility alias
BaseGraphStore = GraphBackend
