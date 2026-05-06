MODELS = {
    "fcm": {
        "name": "Fuzzy Cognitive Map",
        "role": "primary causal simulation engine",
        "interpretable": True,
        "cyclic": True,
        "probabilistic": False,
        "status": "active",
    },
    "bayesian_net": {
        "name": "Bayesian Network",
        "role": "probabilistic sanity-check layer",
        "interpretable": True,
        "cyclic": False,
        "probabilistic": True,
        "status": "candidate",
    },
    "dynamic_bayesian_net": {
        "name": "Dynamic Bayesian Network",
        "role": "time-indexed probabilistic sanity-check layer",
        "interpretable": True,
        "cyclic": False,
        "probabilistic": True,
        "status": "candidate",
    },
    "causal_loop_diagram": {
        "name": "Causal Loop Diagram",
        "role": "qualitative explanation layer",
        "interpretable": True,
        "cyclic": True,
        "probabilistic": False,
        "status": "candidate",
    },
    "neutrosophic_cognitive_map": {
        "name": "Neutrosophic Cognitive Map",
        "role": "indeterminacy-aware causal map",
        "interpretable": True,
        "cyclic": True,
        "probabilistic": False,
        "status": "candidate",
    },
    "knowledge_graph": {
        "name": "Knowledge Graph + Embeddings",
        "role": "retrieval and context grounding layer",
        "interpretable": True,
        "cyclic": True,
        "probabilistic": False,
        "status": "candidate",
    },
    "gnn_rnn": {
        "name": "Graph/Recurrent Neural Network",
        "role": "black-box benchmark only",
        "interpretable": False,
        "cyclic": True,
        "probabilistic": False,
        "status": "defer",
    },
}


def list_candidate_models():
    return {k: v for k, v in MODELS.items() if v["status"] in {"active", "candidate"}}


if __name__ == "__main__":
    for key, model in list_candidate_models().items():
        print(f"{key}: {model['role']}")
