"""Backwards-compatible graph builder wrapper delegating to GraphStore."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.core.logging import profile_stage
from src.db.graph.store import GraphStore

if TYPE_CHECKING:
    from src.ingestion import IngestionResult


class GraphBuilder:
    """Convenience builder wrapper delegating graph construction to GraphStore."""

    @staticmethod
    @profile_stage("graph_builder")
    def build_from_ingestion(
        ingest_result: IngestionResult,
        store: Any | None = None,
    ) -> GraphStore:
        """Construct knowledge graph from ingestion result. Returns a populated GraphStore."""
        if store is not None and isinstance(store, GraphStore):
            graph_store = store
        elif store is not None:
            # Wrap custom backend in GraphStore
            graph_store = GraphStore(backend=store)
        else:
            graph_store = GraphStore.create(backend_type="networkx")

        graph_store.populate_from_ingestion(ingest_result)
        return graph_store
