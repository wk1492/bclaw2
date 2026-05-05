# BCLAW2 Phase 1 - Tests
from validator import validate
from worked_example import EXAMPLE_VALID, EXAMPLE_INVALID

def test_valid():
    ok, msg = validate(EXAMPLE_VALID)
    assert ok is True, f"expected valid, got: {msg}"

def test_invalid():
    ok, msg = validate(EXAMPLE_INVALID)
    assert ok is False, f"expected invalid, got: {msg}"

def test_missing_field():
    record = {k: v for k, v in EXAMPLE_VALID.items() if k != "id"}
    ok, msg = validate(record)
    assert ok is False, f"expected invalid, got: {msg}"

def test_validator_accepts_fused_record():
    from fusion import fuse
    fused = fuse([EXAMPLE_VALID])[0]
    ok, msg = validate(fused)
    assert ok is True, f"expected valid, got: {msg}"

def test_strict_mode():
    record = {**EXAMPLE_VALID, "extra": "field"}
    ok, _ = validate(record)
    assert ok is True, "default mode should accept extra fields"
    ok, msg = validate(record, strict=True)
    assert ok is False, f"strict mode should reject extra fields, got: {msg}"

if __name__ == "__main__":
    test_valid()
    print("PASS: valid example accepted")
    test_invalid()
    print("PASS: invalid example rejected")
    test_missing_field()
    print("PASS: missing required field rejected")
    test_validator_accepts_fused_record()
    print("PASS: validator accepts fused record with extra field")
    test_strict_mode()
    print("PASS: strict mode rejects extra fields, default mode accepts them")
