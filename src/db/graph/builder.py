"""Graph construction coordinator integrating tabular ingestion and causal extractors."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from src.core.logging import get_logger, profile_stage
from src.db.graph.extractors.base import BaseExtractor
from src.db.graph.extractors.financial_rule_extractor import FinancialRuleExtractor
from src.db.graph.extractors.llm_extractor import LLMExtractor
from src.db.graph.store import GraphStore

if TYPE_CHECKING:
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
        self.extractors: list[BaseExtractor] = list(extractors) if extractors else []

    def register_extractor(self, extractor: BaseExtractor) -> None:
        """Register an additional extraction strategy."""
        self.extractors.append(extractor)

    @profile_stage("graph_builder_build")
    def build(
        self,
        ingest_result: IngestionResult,
        run_extractors: bool = True,
    ) -> GraphStore:
        """Populate graph store from ingestion result and execute registered extractors."""
        self.store.populate_from_ingestion(ingest_result)

        if run_extractors and self.extractors:
            filename = ingest_result.metadata.filename
            for extractor in self.extractors:
                try:
                    if isinstance(extractor, LLMExtractor):
                        results = extractor.extract(ingest_result.chunks, source_filename=filename)
                        for disc, edges in results:
                            self.store.add_disclosure_node(disc)
                            for edge in edges:
                                self.store.add_causal_edge(edge)
                    elif isinstance(extractor, FinancialRuleExtractor):
                        # Extract rules over all stored metrics
                        metrics = list(self.store._metrics_cache.values())
                        edges = extractor.extract(metrics)
                        for edge in edges:
                            self.store.add_causal_edge(edge)
                except Exception as exc:
                    logger.warning(f"Extractor {extractor.__class__.__name__} failed during build: {exc}")

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
