import sys

import pytest

import testgen


@pytest.mark.unit
def test_python_version_is_311() -> None:
    assert sys.version_info[:2] == (3, 11)


def test_package_is_importable() -> None:
    assert testgen.__name__ == "testgen"
    assert testgen.__version__ == "0.1.0"


def test_bounded_context_packages_importable() -> None:
    import testgen.api
    import testgen.compliance
    import testgen.generation
    import testgen.ingestion
    import testgen.integrations
    import testgen.knowledge
    import testgen.platform
    import testgen.traceability
    import testgen.ui
    import testgen.worker

    modules = [
        testgen.ingestion,
        testgen.knowledge,
        testgen.generation,
        testgen.traceability,
        testgen.compliance,
        testgen.integrations,
        testgen.api,
        testgen.ui,
        testgen.worker,
        testgen.platform,
    ]
    assert all(module.__doc__ for module in modules)
