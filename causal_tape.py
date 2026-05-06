from graph_state import GraphState, make_graph
from graph_update import graph_update_event, merge_evaluation_snapshot


def replay_snapshots(initial_graph: GraphState, snapshots: list[dict]):
    graph = initial_graph
    events = []
    trajectory = [graph.graph_hash()]

    for index, snapshot in enumerate(snapshots):
        before = graph
        after = merge_evaluation_snapshot(before, snapshot)

        event = graph_update_event(
            before,
            after,
            update_type="evaluation_snapshot_merge",
        )
        event["sequence_index"] = index

        events.append(event)
        trajectory.append(after.graph_hash())
        graph = after

    return {
        "final_graph": graph,
        "trajectory": trajectory,
        "events": events,
    }


def replay_from_empty(snapshots: list[dict], graph_id="causal_tape_graph"):
    return replay_snapshots(make_graph(graph_id), snapshots)
