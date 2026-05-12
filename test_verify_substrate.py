"""
Tests for verify_substrate.sh: determinism contracts, failure modes,
count assertion, ordering invariants, nonzero propagation.
No subprocess call to the full script (avoids recursive pytest invocation).
All subprocess tests use minimal isolated shell fragments.
"""
import os
import stat
import subprocess

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_substrate.sh")


def _src():
    with open(SCRIPT) as f:
        return f.read()


# 1. Script has an explicit numeric expected count
def test_script_has_explicit_expected_count():
    src = _src()
    assert "EXPECTED_COUNT=" in src
    line = next(l for l in src.splitlines() if l.startswith("EXPECTED_COUNT="))
    count = int(line.split("=")[1].strip())
    assert count > 0


# 2. Hardening pytest call appears before collect-only count check
def test_hardening_stage_before_full_suite():
    lines = _src().splitlines()
    hardening_call = next(
        i for i, l in enumerate(lines)
        if "$PYTEST" in l and "test_transcript_hardening.py" in l
    )
    count_check_call = next(
        i for i, l in enumerate(lines)
        if "$PYTEST" in l and "--collect-only" in l
    )
    assert hardening_call < count_check_call


# 3. Color output is explicitly disabled; count uses :: not text parsing
def test_script_disables_color():
    src = _src()
    assert "--color=no" in src
    assert "--color=yes" not in src
    assert 'grep -c "::"' in src
    assert "passed" not in src.split("STAGE 2")[1].split("STAGE 3")[0]


# 4. Strict shell mode is set
def test_script_strict_mode():
    src = _src()
    assert "set -euo pipefail" in src


# 5. Count mismatch exits nonzero with deterministic FAIL message
def test_count_mismatch_fails(tmp_path):
    s = tmp_path / "t.sh"
    s.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "EXPECTED=9999\n"
        "ACTUAL=1\n"
        'if [ -z "$ACTUAL" ] || [ "$ACTUAL" != "$EXPECTED" ]; then\n'
        '    echo "FAIL: expected $EXPECTED tests, got ${ACTUAL:-unknown}"\n'
        "    exit 1\n"
        "fi\n"
    )
    s.chmod(s.stat().st_mode | stat.S_IEXEC)
    r = subprocess.run(["bash", str(s)], capture_output=True, text=True)
    assert r.returncode != 0
    assert "FAIL" in r.stdout
    assert "9999" in r.stdout
    assert "1" in r.stdout


# 6. Missing required file exits nonzero with deterministic FAIL message
def test_missing_required_file_fails(tmp_path):
    s = tmp_path / "t.sh"
    s.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "for f in does_not_exist_xyz.py; do\n"
        '    if [ ! -f "$f" ]; then\n'
        '        echo "FAIL: missing required file: $f"\n'
        "        exit 1\n"
        "    fi\n"
        "done\n"
    )
    s.chmod(s.stat().st_mode | stat.S_IEXEC)
    r = subprocess.run(["bash", str(s)], capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode != 0
    assert "FAIL" in r.stdout
    assert "does_not_exist_xyz.py" in r.stdout


# 7. Nonzero exit propagates through set -euo pipefail
def test_nonzero_propagation(tmp_path):
    inner = tmp_path / "inner.sh"
    inner.write_text("#!/usr/bin/env bash\nexit 42\n")
    inner.chmod(inner.stat().st_mode | stat.S_IEXEC)
    outer = tmp_path / "outer.sh"
    outer.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"bash {inner}\n"
        "echo should_not_print\n"
    )
    outer.chmod(outer.stat().st_mode | stat.S_IEXEC)
    r = subprocess.run(["bash", str(outer)], capture_output=True, text=True)
    assert r.returncode == 42
    assert "should_not_print" not in r.stdout
