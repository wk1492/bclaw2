from serializer_registry import canonical_serialize


def test_dict_order_is_stable():
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    assert canonical_serialize(a) == canonical_serialize(b)


def test_nested_sets_are_stable():
    a = {"items": {"b", "a", "c"}}
    b = {"items": {"c", "b", "a"}}
    assert canonical_serialize(a) == canonical_serialize(b)


def test_float_rounding_is_stable():
    a = {"x": 0.123456789123456}
    b = {"x": 0.123456789123499}
    assert canonical_serialize(a) == canonical_serialize(b)


if __name__ == "__main__":
    test_dict_order_is_stable()
    test_nested_sets_are_stable()
    test_float_rounding_is_stable()
    print("PASS: serializer registry is deterministic")
