import pytest

from testgen.generation.checkpointer import to_psycopg_dsn


@pytest.mark.unit
def test_to_psycopg_dsn_strips_sqlalchemy_dialect_prefix() -> None:
    assert (
        to_psycopg_dsn("postgresql+psycopg://user:pass@localhost:5432/db")
        == "postgresql://user:pass@localhost:5432/db"
    )


@pytest.mark.unit
def test_to_psycopg_dsn_leaves_a_plain_dsn_unchanged() -> None:
    dsn = "postgresql://user:pass@localhost:5432/db"

    assert to_psycopg_dsn(dsn) == dsn
