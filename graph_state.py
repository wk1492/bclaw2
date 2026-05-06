import hashlib
from dataclasses import dataclass, field
from typing import Any

from serializer_registry import canonical_serialize


@dataclass(frozen=True)
class Node:
    node_id: str
    label: str
    activation: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    edge_id: str
    source: str
    target: str
    weight: float
    confidence: float = 1.0
    edge_type: str = "causal"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphState:
    graph_id: str
    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def canonical(self):
        return {
            "graph_id": self.graph_id,
            "metadata": self.metadata,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "label": n.label,
                    "activation": n.activation,
                    "metadata": n.metadata,
                }
                for n in sorted(self.nodes, key=lambda n: n.node_id)
            ],
            "edges": [
                {
                    "edge_id": e.edge_id,
                    "source": e.source,
                    "target": e.target,
                    "weight": e.weight,
                    "confidence": e.confidence,
                    "edge_type": e.edge_type,
                    "metadata": e.metadata,
                }
                for e in sorted(
                    self.edges,
                    key=lambda e: (e.source, e.target, e.edge_type, e.edge_id),
                )
            ],
        }

    def serialize(self):
        return canonical_serialize(self.canonical())

    def graph_hash(self):
        return hashlib.sha256(self.serialize().encode("utf-8")).hexdigest()


def make_graph(graph_id, nodes=None, edges=None, metadata=None):
    return GraphState(
        graph_id=graph_id,
        nodes=tuple(nodes or ()),
        edges=tuple(edges or ()),
        metadata=metadata or {},
    )
