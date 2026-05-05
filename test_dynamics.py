# BCLAW2 Phase 3 - Dynamics Tests
from dynamics import apply_dynamics
from worked_example import EXAMPLE_VALID

def test_dynamics_passthrough():
    records = [EXAMPLE_VALID]
    result = apply_dynamics(records)
    assert result == records, f"expected {records}, got {result}"

def test_dynamics_two_records():
    records = [EXAMPLE_VALID, EXAMPLE_VALID]
    result = apply_dynamics(records)
    assert result == [EXAMPLE_VALID, EXAMPLE_VALID], f"expected {[EXAMPLE_VALID, EXAMPLE_VALID]}, got {result}"

if __name__ == "__main__":
    test_dynamics_passthrough()
    print("PASS: dynamics pass-through verified")
    test_dynamics_two_records()
    print("PASS: dynamics two-record order and contents unchanged")
