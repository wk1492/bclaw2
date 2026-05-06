from graph_state import Edge, Node, make_graph


def snapshot_to_graph(snapshot, graph_id="evaluation_snapshot_graph"):
    candidate_nodes = []
    result_nodes = []
    edges = []

    results = snapshot.get("results", [])
    for idx, result in enumerate(results):
        cid = result.get("id", f"candidate-{idx}")
        valid = bool(result.get("valid"))
        score = float(result.get("score", 1.0 if valid else 0.0))

        candidate_nodes.append(
            Node(
                node_id=f"CANDIDATE::{cid}",
                label=f"candidate {cid}",
                activation=score,
                metadata={"valid": valid},
            )
        )

        result_id = f"RESULT::{cid}"
        result_nodes.append(
            Node(
                node_id=result_id,
                label=f"validation result {cid}",
                activation=1.0 if valid else -1.0,
                metadata={"candidate_id": cid},
            )
        )

        edges.append(
            Edge(
                edge_id=f"EDGE::{cid}::validation",
                source=f"CANDIDATE::{cid}",
                target=result_id,
                weight=1.0 if valid else -1.0,
                confidence=score,
                edge_type="validation",
            )
        )

    return make_graph(
        graph_id=graph_id,
        nodes=tuple(candidate_nodes + result_nodes),
        edges=tuple(edges),
        metadata={"source": "candidate_validation_snapshot"},
    )
