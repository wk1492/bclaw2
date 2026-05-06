from state_serializer import canonical_json, state_hash


def test_dict_order_does_not_change_hash():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}

    assert canonical_json(a) == canonical_json(b)
    assert state_hash(a) == state_hash(b)


def test_float_normalization_is_stable():
    a = {"v": 0.3}
    b = {"v": 0.30000000000000004}

    assert state_hash(a) == state_hash(b)


def test_nested_sets_are_stable():
    a = {"items": {"b", "a"}}
    b = {"items": {"a", "b"}}

    assert state_hash(a) == state_hash(b)


def test_nonfinite_float_rejected():
    try:
        state_hash({"bad": float("nan")})
        raise AssertionError("nan should fail")
    except ValueError:
        pass


if __name__ == "__main__":
    test_dict_order_does_not_change_hash()
    test_float_normalization_is_stable()
    test_nested_sets_are_stable()
    test_nonfinite_float_rejected()
    print("PASS: state serializer tests")
