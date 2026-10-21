"""Graph construction coordinator integrating tabular ingestion and causal extractors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from src.core.logging import get_logger, profile_stage
from src.db.graph.store import GraphStore

if TYPE_CHECKING:
    from src.db.graph.extractors.base import BaseExtractor
    from src.ingestion import IngestionResult

logger = get_logger(__name__)


class GraphBuilder:
    """Convenience builder wrapper delegating graph construction to GraphStore and registered extractors."""

    def __init__(
        self,
        store: GraphStore | None = None,
        extractors: Sequence[BaseExtractor] | None = None,
    ) -> None:
        self.store = store or GraphStore.create(backend_type="networkx")
        self.extractors: list[BaseExtractor] = []
        if extractors:
            for ext in extractors:
                self.register_extractor(ext)

    def register_extractor(self, extractor: BaseExtractor) -> None:
        """Register an additional extraction strategy conforming to the BaseExtractor contract."""
        from src.db.graph.extractors.base import BaseExtractor as BaseExt

        if not isinstance(extractor, BaseExt) and not hasattr(extractor, "apply"):
            raise TypeError(
                f"Unsupported extractor type '{type(extractor).__name__}'. "
                "Registered extractors must implement BaseExtractor or provide an 'apply(store, ingest_result)' method."
            )
        self.extractors.append(extractor)

    @profile_stage("graph_builder_build")
    def build(
        self,
        ingest_result: IngestionResult,
        run_extractors: bool = True,
    ) -> GraphStore:
        """Populate graph store from ingestion result and execute registered extractors via shared apply contract."""
        self.store.populate_from_ingestion(ingest_result)

        if run_extractors and self.extractors:
            for extractor in self.extractors:
                try:
                    extractor.apply(self.store, ingest_result)
                except Exception as exc:
                    logger.warning(
                        f"Extractor {extractor.__class__.__name__} failed during build: {exc}"
                    )

        return self.store

    @staticmethod
    @profile_stage("graph_builder_from_ingest")
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
