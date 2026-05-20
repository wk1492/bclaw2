#!/usr/bin/env python3
"""
BCLAW2 minimal cognition loop demo.

Two agents communicate through an in-memory bus.
Every envelope is appended to demo_transcript.jsonl.
Replay mode reconstructs the same result deterministically.

Usage:
  uv run python bclaw2_demo.py
  uv run python bclaw2_demo.py --replay demo_transcript.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROTOCOL = "agent-protocol-v0.1"
TRANSCRIPT_PATH = Path("demo_transcript.jsonl")

from local_model_runner import run_model as _run_model
_ADAPTER = "local_model_runner.stub"


# ── Canonical envelope ─────────────────────────────────────────────────────────

def make_envelope(
    type_: str,
    sender: str,
    recipient: str,
    task_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "type": type_,
        "sender": sender,
        "recipient": recipient,
        "task_id": task_id,
        "payload": payload,
    }


# ── Transcript ─────────────────────────────────────────────────────────────────

def append_to_transcript(envelope: dict[str, Any], path: Path = TRANSCRIPT_PATH) -> None:
    line = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_transcript(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ── Worker agent ───────────────────────────────────────────────────────────────

def worker_process(prompt: str) -> str:
    result = _run_model("qwen2.5:14b", prompt, backend="stub")
    return result["output_text"]


def worker_agent(bus: list[dict], transcript_path: Path) -> dict[str, Any] | None:
    for i, env in enumerate(bus):
        if env["recipient"] == "worker" and env["type"] == "task_request":
            bus.pop(i)
            output = worker_process(env["payload"].get("prompt", ""))
            response = make_envelope(
                "task_response",
                sender="worker",
                recipient=env["sender"],
                task_id=env["task_id"],
                payload={"result": output, "adapter": _ADAPTER},
            )
            append_to_transcript(response, transcript_path)
            bus.append(response)
            return response
    return None


# ── Orchestrator ───────────────────────────────────────────────────────────────

def orchestrator(
    bus: list[dict],
    task_id: str,
    prompt: str,
    transcript_path: Path,
) -> dict[str, Any]:
    request = make_envelope(
        "task_request",
        sender="orchestrator",
        recipient="worker",
        task_id=task_id,
        payload={"prompt": prompt},
    )
    append_to_transcript(request, transcript_path)
    bus.append(request)

    worker_agent(bus, transcript_path)

    for env in bus:
        if env["recipient"] == "orchestrator" and env["type"] == "task_response":
            return env
    raise RuntimeError("No response received from worker")


# ── Live run ───────────────────────────────────────────────────────────────────

def run_demo(transcript_path: Path = TRANSCRIPT_PATH) -> dict[str, Any]:
    transcript_path.unlink(missing_ok=True)
    bus: list[dict] = []

    result = orchestrator(
        bus,
        task_id="TASK-DEMO-001",
        prompt="Analyze: multi-agent deterministic cognition loop.",
        transcript_path=transcript_path,
    )

    print(f"adapter:    {_ADAPTER}")
    print(f"result:     {result['payload']['result']}")
    print(f"transcript: {transcript_path} ({transcript_path.stat().st_size} bytes)")
    return result


# ── Replay mode ────────────────────────────────────────────────────────────────

def replay_demo(transcript_path: Path) -> dict[str, Any]:
    """Reconstruct final result from transcript. No agents re-run."""
    envelopes = load_transcript(transcript_path)
    if not envelopes:
        raise ValueError(f"Empty or missing transcript: {transcript_path}")

    responses = [e for e in envelopes if e["type"] == "task_response"]
    if not responses:
        raise ValueError("No task_response found in transcript")

    result = responses[-1]
    print(f"[replay] adapter:  {result['payload'].get('adapter')}")
    print(f"[replay] result:   {result['payload']['result']}")
    print(f"[replay] envelopes: {len(envelopes)}")
    return result


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="BCLAW2 minimal cognition loop demo")
    parser.add_argument("--replay", metavar="TRANSCRIPT", help="Replay from transcript file")
    args = parser.parse_args()

    if args.replay:
        replay_demo(Path(args.replay))
    else:
        run_demo()


if __name__ == "__main__":
    main()
