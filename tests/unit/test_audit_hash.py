import pytest

from testgen.platform.audit import GENESIS_HASH, compute_row_hash


@pytest.mark.unit
def test_hash_is_deterministic_and_sha256_shaped() -> None:
    h1 = compute_row_hash(GENESIS_HASH, "test_case.approved", "test_case", "abc-123", {"x": 1})
    h2 = compute_row_hash(GENESIS_HASH, "test_case.approved", "test_case", "abc-123", {"x": 1})

    assert h1 == h2
    assert len(h1) == 64
    int(h1, 16)  # raises ValueError if not valid hex


@pytest.mark.unit
def test_hash_changes_with_payload() -> None:
    h1 = compute_row_hash(GENESIS_HASH, "action", "type", "id", {"x": 1})
    h2 = compute_row_hash(GENESIS_HASH, "action", "type", "id", {"x": 2})

    assert h1 != h2


@pytest.mark.unit
def test_hash_changes_with_prev_hash() -> None:
    h1 = compute_row_hash(GENESIS_HASH, "action", "type", "id", {"x": 1})
    h2 = compute_row_hash("a" * 64, "action", "type", "id", {"x": 1})

    assert h1 != h2


@pytest.mark.unit
def test_payload_key_order_does_not_affect_hash() -> None:
    h1 = compute_row_hash(GENESIS_HASH, "a", "t", "i", {"a": 1, "b": 2})
    h2 = compute_row_hash(GENESIS_HASH, "a", "t", "i", {"b": 2, "a": 1})

    assert h1 == h2
