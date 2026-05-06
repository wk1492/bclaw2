import json
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from pathlib import Path


def now():
    return datetime.now(UTC).isoformat()


def clamp(value, lo=-1.0, hi=1.0):
    return max(lo, min(hi, float(value)))


@dataclass
class GraphNode:
    node_id: str
    label: str
    activation: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    edge_id: str
    source: str
    target: str
    weight: float
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)


class GraphState:
    def __init__(self, graph_id="bclaw2_graph_v1"):
        self.graph_id = graph_id
        self.version = 0
        self.nodes = {}
        self.edges = {}
        self.events = []

    def record(self, event_type, payload):
        self.version += 1
        event = {
            "timestamp": now(),
            "version": self.version,
            "type": event_type,
            "payload": payload,
        }
        self.events.append(event)
        return event

    def add_node(self, node_id, label, activation=0.0, metadata=None):
        if node_id in self.nodes:
            raise ValueError(f"node already exists: {node_id}")
        node = GraphNode(
            node_id=node_id,
            label=label,
            activation=clamp(activation),
            metadata=metadata or {},
        )
        self.nodes[node_id] = node
        self.record("node_added", asdict(node))
        return node

    def add_edge(self, edge_id, source, target, weight, confidence=1.0, metadata=None):
        if edge_id in self.edges:
            raise ValueError(f"edge already exists: {edge_id}")
        if source not in self.nodes:
            raise ValueError(f"missing source node: {source}")
        if target not in self.nodes:
            raise ValueError(f"missing target node: {target}")

        edge = GraphEdge(
            edge_id=edge_id,
            source=source,
            target=target,
            weight=clamp(weight),
            confidence=clamp(confidence, 0.0, 1.0),
            metadata=metadata or {},
        )
        self.edges[edge_id] = edge
        self.record("edge_added", asdict(edge))
        return edge

    def set_activation(self, node_id, activation, source="manual"):
        if node_id not in self.nodes:
            raise ValueError(f"missing node: {node_id}")
        old = self.nodes[node_id].activation
        new = clamp(activation)
        self.nodes[node_id].activation = new
        self.record("activation_updated", {
            "node_id": node_id,
            "old": old,
            "new": new,
            "source": source,
        })
        return new

    def incoming_edges(self, node_id):
        return [e for e in self.edges.values() if e.target == node_id]

    def outgoing_edges(self, node_id):
        return [e for e in self.edges.values() if e.source == node_id]

    def to_dict(self):
        return {
            "graph_id": self.graph_id,
            "version": self.version,
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "edges": {k: asdict(v) for k, v in self.edges.items()},
            "events": self.events,
        }

    def save(self, path="graph_state.json"):
        Path(path).write_text(json.dumps(self.to_dict(), indent=2) + "\n")


if __name__ == "__main__":
    g = GraphState()
    g.add_node("N001", "early pace pressure", 0.7)
    g.add_node("N002", "late fatigue", 0.0)
    g.add_edge("E001", "N001", "N002", 0.8, confidence=0.9)
    g.set_activation("N002", 0.56, source="worked_example")
    g.save()
    print("PASS: graph_state v1 works")
    print(json.dumps(g.to_dict(), indent=2))
