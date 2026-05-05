# BCLAW2 Phase 1 - Minimal Validator
from schema import SCHEMA

def validate(record, strict=False):
    for field in SCHEMA["required"]:
        if field not in record:
            return False, f"missing field: {field}"
    for field, expected_type in SCHEMA["types"].items():
        if field in record and not isinstance(record[field], expected_type):
            return False, f"wrong type: {field}"
    if strict:
        allowed = set(SCHEMA["types"].keys())
        for field in record:
            if field not in allowed:
                return False, f"unexpected field: {field}"
    return True, "ok"
