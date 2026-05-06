import json
from dataclasses import asdict, is_dataclass


class SerializerRegistry:
    def __init__(self):
        self._serializers = {}

    def register(self, typ, fn):
        self._serializers[typ] = fn

    def normalize(self, obj):
        for typ, fn in self._serializers.items():
            if isinstance(obj, typ):
                return self.normalize(fn(obj))

        if is_dataclass(obj):
            return self.normalize(asdict(obj))

        if isinstance(obj, dict):
            return {
                str(k): self.normalize(v)
                for k, v in sorted(obj.items(), key=lambda item: str(item[0]))
            }

        if isinstance(obj, (list, tuple)):
            return [self.normalize(v) for v in obj]

        if isinstance(obj, set):
            return sorted(self.normalize(v) for v in obj)

        if isinstance(obj, float):
            return round(obj, 12)

        return obj

    def serialize(self, obj):
        return json.dumps(
            self.normalize(obj),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )


registry = SerializerRegistry()


def canonical_serialize(obj):
    return registry.serialize(obj)
