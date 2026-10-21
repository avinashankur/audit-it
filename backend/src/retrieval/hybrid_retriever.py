"""Hybrid retriever combining in-memory text search and graph traversal."""

from typing import Any

from src.core.logging import get_logger, profile_stage
from src.db.graph.store import GraphStore
from src.db.models.entities import (
    CausalGraphPath,
    FinancialMetricNode,
    HybridRetrievalResult,
    TextChunk,
)
from src.retrieval.vector_store import VectorStore

logger = get_logger(__name__)


class HybridRetriever:
    """Coordinates vector text similarity and graph traversal for unified audit retrieval."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        graph_store: Any | None = None,
    ) -> None:
        self.vector_store = vector_store or VectorStore()
        if graph_store is None:
            self.graph_store = GraphStore.create(backend_type="networkx")
        elif isinstance(graph_store, GraphStore):
            self.graph_store = graph_store
        else:
            self.graph_store = GraphStore(backend=graph_store)

    @profile_stage("hybrid_retrieve")
    def retrieve(
        self,
        query: str,
        top_k_chunks: int = 5,
        max_hops: int = 2,
    ) -> HybridRetrievalResult:
        """Execute parallel lexical text search and knowledge graph traversal.

        Args:
            query: User's financial audit question.
            top_k_chunks: Number of relevant text chunks to return.
            max_hops: Maximum graph traversal distance for causal dependencies.

        Returns:
            HybridRetrievalResult with chunks, metric nodes, and causal paths.
        """
        # 1. Text Similarity Search
        scored_chunks = self.vector_store.search(query=query, top_k=top_k_chunks)
        chunks = [c for c, _ in scored_chunks]
        rrf_scores = {c.chunk_id: score for c, score in scored_chunks}

        # 2. Graph Traversal via Deep GraphStore Interface
        metric_nodes, unique_paths = self.graph_store.find_causal_neighborhood(
            query_text=query,
            max_hops=max_hops,
        )

        logger.info(
            f"Retrieved {len(chunks)} chunks, {len(metric_nodes)} metric nodes, "
            f"and {len(unique_paths)} causal paths for query: '{query[:40]}...'"
        )

        return HybridRetrievalResult(
            query=query,
            text_chunks=chunks,
            metric_nodes=metric_nodes,
            causal_paths=unique_paths,
            rrf_scores=rrf_scores,
        )
