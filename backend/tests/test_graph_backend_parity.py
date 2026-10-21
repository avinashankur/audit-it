"""Parity test suite ensuring behavioral parity across graph storage adapters."""

import pytest

from src.db.graph.storage.neo4j_adapter import Neo4jBackend
from src.db.graph.storage.networkx_store import NetworkXBackend


@pytest.fixture(params=["networkx", "neo4j"])
def backend(request):
    """Instantiate each backend adapter for identical parity testing."""
    if request.param == "networkx":
        b = NetworkXBackend()
    else:
        # Without password, Neo4jBackend uses verified in-memory fallback
        b = Neo4jBackend(password=None, fallback_to_memory=True)
    b.clear()
    yield b
    b.clear()


def test_node_lifecycle_parity(backend):
    """Verify upsert_node and get_node produce identical results across backends."""
    backend.upsert_node(
        node_id="rev_node",
        label="METRIC",
        properties={"name": "Revenue", "value": 1500.0, "period": "2023"},
    )

    node = backend.get_node("rev_node")
    assert node is not None
    assert node["name"] == "Revenue"
    assert node["value"] == 1500.0
    assert node["period"] == "2023"
    assert node["node_id"] == "rev_node"


def test_edge_and_neighbors_parity(backend):
    """Verify upsert_edge and get_neighbors produce identical traversal results."""
    backend.upsert_node("rev", "METRIC", {"name": "Revenue"})
    backend.upsert_node("gm", "METRIC", {"name": "Gross Margin"})
    backend.upsert_edge(
        source_id="rev",
        target_id="gm",
        relation_type="DRIVES",
        properties={"confidence": 1.0, "evidence": "Direct flow"},
    )

    downstream = backend.get_neighbors("rev", direction="downstream")
    assert len(downstream) == 1
    assert downstream[0]["node"]["node_id"] == "gm"
    assert downstream[0]["edge"]["relation_type"] == "DRIVES"

    upstream = backend.get_neighbors("gm", direction="upstream")
    assert len(upstream) == 1
    assert upstream[0]["node"]["node_id"] == "rev"


def test_multi_hop_path_finding_parity(backend):
    """Verify multi-hop path resolution between endpoints across backends."""
    backend.upsert_node("rev", "METRIC", {"name": "Revenue"})
    backend.upsert_node("gm", "METRIC", {"name": "Gross Margin"})
    backend.upsert_node("oi", "METRIC", {"name": "Operating Income"})

    backend.upsert_edge("rev", "gm", "DRIVES", {"confidence": 1.0})
    backend.upsert_edge("gm", "oi", "DRIVES", {"confidence": 1.0})

    paths = backend.find_paths("rev", "oi", max_depth=3)
    assert len(paths) == 1
    assert paths[0]["nodes"] == ["rev", "gm", "oi"]
    assert paths[0]["length"] == 2


def test_subgraph_and_stats_parity(backend):
    """Verify subgraph extraction and statistical counts parity."""
    backend.upsert_node("rev", "METRIC", {"name": "Revenue"})
    backend.upsert_node("disc_1", "DISCLOSURE", {"name": "Accounting Policy"})
    backend.upsert_edge("rev", "disc_1", "EXPLAINS", {})

    stats = backend.get_stats()
    assert stats["total_nodes"] == 2
    assert stats["metric_nodes"] == 1
    assert stats["disclosure_nodes"] == 1
    assert stats["causal_edges"] == 1

    subgraph = backend.get_subgraph(root_id="rev", hops=1)
    node_ids = {n.get("node_id") for n in subgraph["nodes"]}
    assert "rev" in node_ids
    assert "disc_1" in node_ids
