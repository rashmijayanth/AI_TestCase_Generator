"""Shared fixtures for integration tests: a real-Postgres-backed session per test,
wrapped in a transaction that is always rolled back so tests never leave data behind.
"""

from collections.abc import Generator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# Import every bounded context's models so Base.metadata is complete before create_all.
from testgen.compliance import models as _compliance_models  # noqa: F401
from testgen.generation import models as _generation_models  # noqa: F401
from testgen.ingestion import models as _ingestion_models  # noqa: F401
from testgen.integrations import models as _integrations_models  # noqa: F401
from testgen.platform import models as _platform_models  # noqa: F401
from testgen.platform.db.base import Base
from testgen.platform.db.session import get_engine
from testgen.traceability import models as _traceability_models  # noqa: F401


@pytest.fixture(scope="session")
def db_engine() -> Engine:
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    connection = db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        # A flush error (e.g. an expected IntegrityError) makes SQLAlchemy roll back
        # this same connection-bound transaction internally; guard against rolling
        # back an already-inactive transaction a second time.
        if transaction.is_active:
            transaction.rollback()
        connection.close()
