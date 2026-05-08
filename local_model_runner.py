import hashlib
import json


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _output_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _run_stub(model_name: str, prompt: str, **kwargs) -> dict:
    ph = _prompt_hash(prompt)
    output_text = f"[STUB:{model_name}] prompt_hash={ph[:12]}"
    return {
        "model_name": model_name,
        "prompt_hash": ph,
        "output_text": output_text,
        "output_hash": _output_hash(output_text),
        "status": "ok",
        "error": None,
    }


def _run_ollama(model_name: str, prompt: str, host: str = "http://localhost:11434", **kwargs) -> dict:
    import urllib.request
    ph = _prompt_hash(prompt)
    try:
        body = json.dumps({"model": model_name, "prompt": prompt, "stream": False}).encode("utf-8")
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        output_text = data.get("response", "")
        return {
            "model_name": model_name,
            "prompt_hash": ph,
            "output_text": output_text,
            "output_hash": _output_hash(output_text),
            "status": "ok",
            "error": None,
        }
    except Exception as exc:
        return {
            "model_name": model_name,
            "prompt_hash": ph,
            "output_text": "",
            "output_hash": _output_hash(""),
            "status": "error",
            "error": str(exc),
        }


BACKENDS = {
    "stub": _run_stub,
    "ollama": _run_ollama,
}


def run_model(model_name: str, prompt: str, backend: str = "stub", **kwargs) -> dict:
    if backend not in BACKENDS:
        raise ValueError(f"Unknown backend {backend!r}. Valid: {sorted(BACKENDS)}")
    result = BACKENDS[backend](model_name, prompt, **kwargs)
    _validate_result(result)
    return result


def _validate_result(result: dict) -> None:
    required = {"model_name", "prompt_hash", "output_text", "output_hash", "status", "error"}
    missing = required - set(result.keys())
    if missing:
        raise ValueError(f"Model result missing fields: {missing}")
    if result["status"] not in {"ok", "error"}:
        raise ValueError(f"Invalid status: {result['status']!r}")


if __name__ == "__main__":
    r = run_model("test-model", "hello world", backend="stub")
    print(r)
    assert r["status"] == "ok"
    assert r["prompt_hash"] == _prompt_hash("hello world")
    print("PASS: local_model_runner stub backend")
