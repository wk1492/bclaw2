from fcm_dynamics import apply_fcm_step, apply_fcm_steps
from graph_state import Edge, Node, make_graph


def sample_graph():
    return make_graph(
        "g",
        nodes=[
            Node("A", "early pace pressure", 0.7),
            Node("B", "late fatigue", 0.0),
            Node("C", "finish strength", 0.4),
        ],
        edges=[
            Edge("E1", "A", "B", 0.8, confidence=0.9),
            Edge("E2", "B", "C", -0.5, confidence=0.7),
        ],
    )


def test_same_graph_same_step_same_hash():
    g1 = sample_graph()
    g2 = sample_graph()

    assert apply_fcm_step(g1).graph_hash() == apply_fcm_step(g2).graph_hash()


def test_same_graph_same_step_count_same_trajectory():
    g1 = sample_graph()
    g2 = sample_graph()

    a = apply_fcm_steps(g1, steps=3)
    b = apply_fcm_steps(g2, steps=3)

    assert a["trajectory"] == b["trajectory"]
    assert a["final_graph"].graph_hash() == b["final_graph"].graph_hash()


def test_activation_is_bounded():
    g = make_graph(
        "g",
        nodes=[Node("A", "cause", 1.0), Node("B", "effect", 0.9)],
        edges=[Edge("E1", "A", "B", 10.0, confidence=1.0)],
    )

    out = apply_fcm_step(g)
    node_b = [n for n in out.nodes if n.node_id == "B"][0]
    assert node_b.activation == 1.0


if __name__ == "__main__":
    test_same_graph_same_step_same_hash()
    test_same_graph_same_step_count_same_trajectory()
    test_activation_is_bounded()
    print("PASS: deterministic FCM dynamics")
