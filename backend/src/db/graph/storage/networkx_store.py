"""In-memory directed financial knowledge graph using NetworkX."""

from typing import Any

import networkx as nx

from src.db.graph.storage.base import GraphBackend


def normalize_lookup_key(text: str) -> str:
    """Normalize metric or node names for deterministic lookup."""
    return text.strip().lower().replace(" ", "_").replace("-", "_").replace(".", "")


class NetworkXBackend(GraphBackend):
    """In-memory property graph engine using NetworkX. Optimized for testing and local execution."""

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()

    def upsert_node(self, node_id: str, label: str, properties: dict[str, Any]) -> None:
        """Insert or update a node with the given label and properties."""
        props = dict(properties)
        props["node_id"] = node_id
        props["label"] = label
        props["node_type"] = label  # backwards-compatible alias
        self.graph.add_node(node_id, **props)

    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: dict[str, Any],
    ) -> None:
        """Insert or update a directed relationship edge between two nodes."""
        if source_id not in self.graph:
            self.upsert_node(source_id, "METRIC", {"name": source_id})
        if target_id not in self.graph:
            self.upsert_node(target_id, "METRIC", {"name": target_id})

        props = dict(properties)
        props["relation_type"] = relation_type
        self.graph.add_edge(source_id, target_id, **props)

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve node attributes by node_id."""
        if node_id in self.graph:
            data = dict(self.graph.nodes[node_id])
            data["node_id"] = node_id
            return data
        return None

    def get_neighbors(
        self,
        node_id: str,
        direction: str = "downstream",
    ) -> list[dict[str, Any]]:
        """Retrieve immediate neighbor nodes and connecting relationships."""
        if node_id not in self.graph:
            return []

        neighbors: list[dict[str, Any]] = []

        if direction in ("downstream", "both"):
            for succ in self.graph.successors(node_id):
                edge_data = dict(self.graph.edges[node_id, succ])
                node_data = dict(self.graph.nodes[succ])
                node_data["node_id"] = succ
                neighbors.append({
                    "node": node_data,
                    "edge": edge_data,
                    "direction": "downstream",
                })

        if direction in ("upstream", "both"):
            for pred in self.graph.predecessors(node_id):
                edge_data = dict(self.graph.edges[pred, node_id])
                node_data = dict(self.graph.nodes[pred])
                node_data["node_id"] = pred
                neighbors.append({
                    "node": node_data,
                    "edge": edge_data,
                    "direction": "upstream",
                })

        return neighbors

    def find_paths(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 3,
    ) -> list[dict[str, Any]]:
        """Find all directed paths between source and target up to max_depth."""
        if source_id not in self.graph or target_id not in self.graph:
            return []

        try:
            raw_paths = list(
                nx.all_simple_paths(
                    self.graph,
                    source=source_id,
                    target=target_id,
                    cutoff=max_depth,
                )
            )
        except Exception:
            return []

        structured_paths: list[dict[str, Any]] = []
        for path_nodes in raw_paths:
            edges: list[dict[str, Any]] = []
            for u, v in zip(path_nodes[:-1], path_nodes[1:], strict=False):
                edge_props = dict(self.graph.edges[u, v])
                edges.append({
                    "source": u,
                    "target": v,
                    "relation_type": edge_props.get("relation_type", "DRIVES"),
                    "properties": edge_props,
                })
            structured_paths.append({
                "nodes": path_nodes,
                "edges": edges,
                "length": len(path_nodes) - 1,
            })

        return structured_paths

    def get_subgraph(
        self,
        root_id: str | None = None,
        hops: int = 2,
    ) -> dict[str, Any]:
        """Return nodes and edges within `hops` distance from `root_id` (or all if root_id is None)."""
        if not root_id or root_id not in self.graph:
            # Return full graph
            nodes = [
                {**dict(self.graph.nodes[n]), "id": n, "node_id": n}
                for n in self.graph.nodes
            ]
            edges = [
                {
                    "source": u,
                    "target": v,
                    "relation_type": self.graph.edges[u, v].get("relation_type", "RELATED"),
                    **dict(self.graph.edges[u, v]),
                }
                for u, v in self.graph.edges
            ]
            return {"nodes": nodes, "edges": edges}

        # BFS expansion
        visited: set[str] = {root_id}
        frontier: set[str] = {root_id}

        for _ in range(hops):
            next_frontier: set[str] = set()
            for node in frontier:
                successors = set(self.graph.successors(node))
                predecessors = set(self.graph.predecessors(node))
                next_frontier.update((successors | predecessors) - visited)
            visited.update(next_frontier)
            frontier = next_frontier
            if not frontier:
                break

        sub = self.graph.subgraph(visited)
        nodes = [{**dict(sub.nodes[n]), "id": n, "node_id": n} for n in sub.nodes]
        edges = [
            {
                "source": u,
                "target": v,
                "relation_type": sub.edges[u, v].get("relation_type", "RELATED"),
                **dict(sub.edges[u, v]),
            }
            for u, v in sub.edges
        ]
        return {"nodes": nodes, "edges": edges}

    def get_stats(self) -> dict[str, int]:
        """Return counts of total nodes, metric nodes, disclosure nodes, and causal edges."""
        metric_count = 0
        disclosure_count = 0

        for _, data in self.graph.nodes(data=True):
            lbl = (data.get("label") or data.get("node_type") or "").upper()
            if lbl == "METRIC":
                metric_count += 1
            elif lbl == "DISCLOSURE":
                disclosure_count += 1

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "metric_nodes": metric_count,
            "disclosure_nodes": disclosure_count,
            "causal_edges": self.graph.number_of_edges(),
        }

    def clear(self) -> None:
        """Clear all nodes and edges from storage."""
        self.graph.clear()

    # --- Backwards Compatibility Wrappers ---
    def add_node(self, node_id: str, node_type: str, properties: dict[str, Any]) -> None:
        self.upsert_node(node_id, node_type, properties)

    def add_edge(self, source_id: str, target_id: str, relationship: str, properties: dict[str, Any]) -> None:
        self.upsert_edge(source_id, target_id, relationship, properties)

    def get_subgraph_data(self, root_node: str | None = None, hops: int = 2) -> dict[str, Any]:
        return self.get_subgraph(root_node, hops)


# Backwards compatibility alias
NetworkXStore = NetworkXBackend
