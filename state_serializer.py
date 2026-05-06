import hashlib
import json
from decimal import Decimal
from math import isfinite


FLOAT_QUANT = Decimal("0.0000000001")


def normalize_value(value):
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError(f"non-finite float not allowed: {value}")
        return str(Decimal(str(value)).quantize(FLOAT_QUANT))

    if isinstance(value, dict):
        return {
            str(k): normalize_value(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }

    if isinstance(value, (list, tuple)):
        return [normalize_value(v) for v in value]

    if isinstance(value, set):
        return sorted(normalize_value(v) for v in value)

    return value


def canonical_json(state):
    normalized = normalize_value(state)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def state_hash(state):
    return hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    demo = {
        "b": 2,
        "a": {
            "float": 0.1 + 0.2,
            "items": {"z", "a"},
        },
    }

    print(canonical_json(demo))
    print(state_hash(demo))
