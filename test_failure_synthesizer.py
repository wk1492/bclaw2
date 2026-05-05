from failure_synthesizer import synthesize


def test_git_failures_suggest_safe_push():
    results = synthesize("repository not found; unable to add remote; no configured push destination")
    assert results
    assert results[0]["pattern_id"] == "git_state_normalization"
    assert results[0]["artifact"] == "git_safe_push.sh"
    print("PASS: failure synthesizer proposes next rung")


if __name__ == "__main__":
    test_git_failures_suggest_safe_push()
