from graph_state import clamp


def disagreement_score(proposals):
    weights = [float(p["weight"]) for p in proposals]
    if not weights:
        return 0.0
    return round(max(weights) - min(weights), 6)


def arbitrate_edge(edge_id, source, target, proposals):
    if not proposals:
        raise ValueError("no edge proposals supplied")

    total_confidence = sum(float(p.get("confidence", 0.0)) for p in proposals)
    if total_confidence <= 0:
        raise ValueError("total confidence must be positive")

    weighted_sum = sum(
        float(p["weight"]) * float(p.get("confidence", 0.0))
        for p in proposals
    )

    final_weight = clamp(weighted_sum / total_confidence)
    final_confidence = clamp(total_confidence / len(proposals), 0.0, 1.0)

    return {
        "edge_id": edge_id,
        "source": source,
        "target": target,
        "final_weight": round(final_weight, 6),
        "final_confidence": round(final_confidence, 6),
        "disagreement": disagreement_score(proposals),
        "contributors": proposals,
    }


if __name__ == "__main__":
    result = arbitrate_edge(
        "E001",
        "N001",
        "N002",
        [
            {"agent": "grok", "weight": 0.8, "confidence": 0.9},
            {"agent": "claude", "weight": 0.6, "confidence": 0.7},
        ],
    )
    print(result)
