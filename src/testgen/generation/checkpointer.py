"""Persistent, Postgres-backed LangGraph checkpointer for real deployments.

InMemorySaver (used in Phase 4's own tests) doesn't survive a process restart.
A real deployment needs a paused human-approval interrupt to survive between
the request that triggers generation and the later, separate request where a
human actually approves it -- confirmed to work exactly this way with a
throwaway script (two independent PostgresSaver instances, simulating two
separate processes, both talking to the same Postgres container) before
writing this wrapper. See docs/PROGRESS.md.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver

from testgen.platform.config import Settings, get_settings


def to_psycopg_dsn(sqlalchemy_url: str) -> str:
    """langgraph-checkpoint-postgres uses psycopg directly and expects a plain
    postgresql:// DSN, not SQLAlchemy's postgresql+psycopg:// dialect prefix
    (confirmed directly against the real driver).
    """
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def postgres_checkpointer(settings: Settings | None = None) -> Iterator[PostgresSaver]:
    settings = settings or get_settings()
    dsn = to_psycopg_dsn(settings.database_url)
    with PostgresSaver.from_conn_string(dsn) as checkpointer:
        checkpointer.setup()
        yield checkpointer
