# BCLAW2 Phase 1 - Schema loader
import json

_TYPE_MAP = {"str": str, "int": int, "float": float}

def _load():
    with open("schema_def.json") as f:
        raw = json.load(f)
    types = {}
    for field, t in raw["types"].items():
        if isinstance(t, list):
            types[field] = tuple(_TYPE_MAP[x] for x in t)
        else:
            types[field] = _TYPE_MAP[t]
    return {"required": raw["required"], "types": types}

SCHEMA = _load()
