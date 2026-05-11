import hashlib
from typing import Any

from serializer_registry import canonical_serialize


def clamp(value, lo=0.0, hi=1.0):
    return max(lo, min(hi, value))


class Node:
    __slots__ = ("node_id", "label", "activation", "metadata")

    def __init__(self, node_id: str, label: str, activation: float = 0.0, metadata: dict = None):
        self.node_id = node_id
        self.label = label
        self.activation = activation
        self.metadata = metadata if metadata is not None else {}


class Edge:
    __slots__ = ("edge_id", "source", "target", "weight", "confidence", "edge_type", "metadata")

    def __init__(self, edge_id: str, source: str, target: str, weight: float,
                 confidence: float = 1.0, edge_type: str = "causal", metadata: dict = None):
        self.edge_id = edge_id
        self.source = source
        self.target = target
        self.weight = weight
        self.confidence = confidence
        self.edge_type = edge_type
        self.metadata = metadata if metadata is not None else {}


class NodeMap(dict):
    """Dict[node_id -> Node] that iterates Node objects (values) by default."""
    def __iter__(self):
        yield from self.values()


class GraphState:
    def __init__(self, graph_id: str = "", nodes=None, edges=None, metadata: dict = None):
        self.graph_id = graph_id
        self.metadata = metadata if metadata is not None else {}
        self._nodes: NodeMap = NodeMap()
        self._edges: list = []
        for n in (nodes or ()):
            self._nodes[n.node_id] = n
        for e in (edges or ()):
            self._edges.append(e)

    @property
    def nodes(self) -> NodeMap:
        return self._nodes

    @property
    def edges(self) -> list:
        return self._edges

    def add_node(self, node_id: str, label: str, activation: float = 0.0):
        self._nodes[node_id] = Node(node_id=node_id, label=label, activation=activation)

    def add_edge(self, edge_id: str, source: str, target: str, weight: float):
        self._edges.append(Edge(edge_id=edge_id, source=source, target=target, weight=weight))

    def set_activation(self, node_id: str, value: float, source: str = None):
        old = self._nodes[node_id]
        self._nodes[node_id] = Node(
            node_id=old.node_id, label=old.label, activation=value, metadata=old.metadata
        )

    def incoming_edges(self, node_id: str) -> list:
        return [e for e in self._edges if e.target == node_id]

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
                for n in sorted(self._nodes.values(), key=lambda n: n.node_id)
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
                    self._edges,
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
        nodes=nodes or (),
        edges=edges or (),
        metadata=metadata or {},
    )
