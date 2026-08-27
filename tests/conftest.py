"""Root conftest — applies to both tests/unit and tests/integration."""

import pytest

from testgen.platform.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """get_settings() is lru_cache'd for production; without this, whichever test
    calls it first would leak its cached Settings into every later test.
    """
    get_settings.cache_clear()
