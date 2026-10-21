"""Persistent property graph engine using Neo4j with real Cypher execution."""

import re
from typing import Any

from src.core.exceptions import Neo4jConnectionError
from src.core.logging import get_logger
from src.db.graph.storage.base import GraphBackend
from src.db.graph.storage.networkx_store import NetworkXBackend

logger = get_logger(__name__)


def _sanitize_cypher_identifier(name: str, fallback: str) -> str:
    """Sanitize strings for Cypher label and relationship type interpolation."""
    clean = re.sub(r"[^A-Za-z0-9_]", "", name or "")
    return clean if clean else fallback


class Neo4jBackend(GraphBackend):
    """Persistent graph adapter executing Cypher statements with in-memory NetworkX fallback."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str | None = None,
        fallback_to_memory: bool = True,
    ) -> None:
        self.uri = uri
        self.user = user
        self.fallback_to_memory = fallback_to_memory
        self._fallback = NetworkXBackend()
        self._driver: Any = None
        self._connected = False

        if password:
            self._connect(password)
        else:
            logger.info("No Neo4j password provided; operating with in-memory NetworkX fallback.")

    def _connect(self, password: str) -> None:
        try:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, password))
            self._driver.verify_connectivity()
            self._connected = True
            logger.info(f"Connected to Neo4j instance at {self.uri}")
        except Exception as exc:
            if not self.fallback_to_memory:
                raise Neo4jConnectionError(f"Failed to connect to Neo4j: {exc}") from exc
            logger.warning(f"Neo4j connection failed ({exc}); falling back to in-memory graph store.")
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """True if successfully connected to live Neo4j instance."""
        return self._connected

    def upsert_node(self, node_id: str, label: str, properties: dict[str, Any]) -> None:
        """Insert or update a node with the given label and properties."""
        if not self._connected:
            self._fallback.upsert_node(node_id, label, properties)
            return

        clean_label = _sanitize_cypher_identifier(label, "METRIC")
        props = dict(properties)
        props["node_id"] = node_id
        props["label"] = clean_label

        cypher = f"""
        MERGE (n:{clean_label} {{node_id: $node_id}})
        SET n += $properties
        """
        with self._driver.session() as session:
            session.run(cypher, node_id=node_id, properties=props)

    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: dict[str, Any],
    ) -> None:
        """Insert or update a directed relationship edge between two nodes."""
        if not self._connected:
            self._fallback.upsert_edge(source_id, target_id, relation_type, properties)
            return

        clean_rel = _sanitize_cypher_identifier(relation_type, "DRIVES")
        props = dict(properties)
        props["relation_type"] = clean_rel

        cypher = f"""
        MERGE (s {{node_id: $source_id}})
        MERGE (t {{node_id: $target_id}})
        MERGE (s)-[r:{clean_rel}]->(t)
        SET r += $properties
        """
        with self._driver.session() as session:
            session.run(cypher, source_id=source_id, target_id=target_id, properties=props)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve node attributes by node_id."""
        if not self._connected:
            return self._fallback.get_node(node_id)

        cypher = """
        MATCH (n {node_id: $node_id})
        RETURN properties(n) AS props, labels(n) AS labels
        LIMIT 1
        """
        with self._driver.session() as session:
            result = session.run(cypher, node_id=node_id)
            record = result.single()
            if record:
                data = dict(record["props"])
                labels = record["labels"]
                if labels and "label" not in data:
                    data["label"] = labels[0]
                data["node_id"] = node_id
                return data
        return None

    def get_neighbors(
        self,
        node_id: str,
        direction: str = "downstream",
    ) -> list[dict[str, Any]]:
        """Retrieve immediate neighbor nodes and connecting relationships."""
        if not self._connected:
            return self._fallback.get_neighbors(node_id, direction)

        neighbors: list[dict[str, Any]] = []

        if direction in ("downstream", "both"):
            cypher_down = """
            MATCH (s {node_id: $node_id})-[r]->(t)
            RETURN properties(t) AS node, properties(r) AS edge, type(r) AS rel_type, 'downstream' AS direction
            """
            with self._driver.session() as session:
                for rec in session.run(cypher_down, node_id=node_id):
                    edge_dict = dict(rec["edge"])
                    edge_dict["relation_type"] = rec["rel_type"]
                    neighbors.append({
                        "node": dict(rec["node"]),
                        "edge": edge_dict,
                        "direction": "downstream",
                    })

        if direction in ("upstream", "both"):
            cypher_up = """
            MATCH (s {node_id: $node_id})<-[r]-(t)
            RETURN properties(t) AS node, properties(r) AS edge, type(r) AS rel_type, 'upstream' AS direction
            """
            with self._driver.session() as session:
                for rec in session.run(cypher_up, node_id=node_id):
                    edge_dict = dict(rec["edge"])
                    edge_dict["relation_type"] = rec["rel_type"]
                    neighbors.append({
                        "node": dict(rec["node"]),
                        "edge": edge_dict,
                        "direction": "upstream",
                    })

        return neighbors

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 3,
    ) -> list[dict[str, Any]]:
        """Find all directed paths between source and target up to max_depth using Cypher."""
        if not self._connected:
            return self._fallback.find_paths(source_id, target_id, max_depth)

        safe_depth = max(1, min(max_depth, 6))
        cypher = f"""
        MATCH p = (s {{node_id: $source_id}})-[*1..{safe_depth}]->(t {{node_id: $target_id}})
        RETURN [n IN nodes(p) | n.node_id] AS path_nodes,
               [r IN relationships(p) | {{
                   source: startNode(r).node_id,
                   target: endNode(r).node_id,
                   relation_type: type(r),
                   properties: properties(r)
               }}] AS path_edges
        LIMIT 20
        """
        paths: list[dict[str, Any]] = []
        with self._driver.session() as session:
            for rec in session.run(cypher, source_id=source_id, target_id=target_id):
                paths.append({
                    "nodes": list(rec["path_nodes"]),
                    "edges": list(rec["path_edges"]),
                    "length": len(rec["path_nodes"]) - 1,
                })
        return paths

    def get_subgraph(
        self,
        root_id: str | None = None,
        hops: int = 2,
    ) -> dict[str, Any]:
        """Return nodes and edges within `hops` distance from `root_id`."""
        if not self._connected:
            return self._fallback.get_subgraph(root_id, hops)

        if not root_id:
            cypher = """
            MATCH (n)
            OPTIONAL MATCH (n)-[r]->(m)
            RETURN collect(DISTINCT properties(n)) AS nodes,
                   collect(DISTINCT {source: startNode(r).node_id, target: endNode(r).node_id, relation_type: type(r)}) AS edges
            """
            with self._driver.session() as session:
                rec = session.run(cypher).single()
                if rec:
                    return {"nodes": list(rec["nodes"]), "edges": [e for e in rec["edges"] if e.get("source")]}
            return {"nodes": [], "edges": []}

        safe_hops = max(1, min(hops, 4))
        cypher = f"""
        MATCH (root {{node_id: $root_id}})-[*0..{safe_hops}]-(n)
        WITH collect(DISTINCT n) AS neighborhood
        UNWIND neighborhood AS n
        OPTIONAL MATCH (n)-[r]->(m)
        WHERE m IN neighborhood
        RETURN collect(DISTINCT properties(n)) AS nodes,
               collect(DISTINCT {{source: startNode(r).node_id, target: endNode(r).node_id, relation_type: type(r)}}) AS edges
        """
        with self._driver.session() as session:
            rec = session.run(cypher, root_id=root_id).single()
            if rec:
                return {"nodes": list(rec["nodes"]), "edges": [e for e in rec["edges"] if e.get("source")]}
        return {"nodes": [], "edges": []}

    def get_stats(self) -> dict[str, int]:
        """Return counts of total nodes, metric nodes, disclosure nodes, and causal edges."""
        if not self._connected:
            return self._fallback.get_stats()

        cypher = """
        MATCH (n) WITH count(n) AS total_nodes
        OPTIONAL MATCH (m:METRIC) WITH total_nodes, count(m) AS metric_nodes
        OPTIONAL MATCH (d:DISCLOSURE) WITH total_nodes, metric_nodes, count(d) AS disclosure_nodes
        OPTIONAL MATCH ()-[r]->() WITH total_nodes, metric_nodes, disclosure_nodes, count(r) AS causal_edges
        RETURN total_nodes, metric_nodes, disclosure_nodes, causal_edges
        """
        with self._driver.session() as session:
            rec = session.run(cypher).single()
            if rec:
                return {
                    "total_nodes": int(rec["total_nodes"] or 0),
                    "metric_nodes": int(rec["metric_nodes"] or 0),
                    "disclosure_nodes": int(rec["disclosure_nodes"] or 0),
                    "causal_edges": int(rec["causal_edges"] or 0),
                }
        return {"total_nodes": 0, "metric_nodes": 0, "disclosure_nodes": 0, "causal_edges": 0}

    def clear(self) -> None:
        """Clear all nodes and edges from storage."""
        if not self._connected:
            self._fallback.clear()
            return

        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def close(self) -> None:
        """Close active Neo4j driver connection."""
        if self._driver:
            self._driver.close()
            self._connected = False


# Backwards compatibility alias
Neo4jAdapter = Neo4jBackend
