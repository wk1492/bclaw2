from verify_system import assert_serializer, assert_checkpoint


def test_serializer_check():
    assert_serializer()


def test_checkpoint_check():
    assert_checkpoint()


if __name__ == "__main__":
    test_serializer_check()
    test_checkpoint_check()
    print("PASS: verify_system tests")
