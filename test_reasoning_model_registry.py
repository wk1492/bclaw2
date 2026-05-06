from reasoning_model_registry import MODELS, list_candidate_models


def test_fcm_is_active():
    assert MODELS["fcm"]["status"] == "active"


def test_black_box_models_deferred():
    assert MODELS["gnn_rnn"]["status"] == "defer"


def test_candidates_available():
    candidates = list_candidate_models()
    assert "bayesian_net" in candidates
    assert "neutrosophic_cognitive_map" in candidates


if __name__ == "__main__":
    test_fcm_is_active()
    test_black_box_models_deferred()
    test_candidates_available()
    print("PASS: reasoning model registry tests")
