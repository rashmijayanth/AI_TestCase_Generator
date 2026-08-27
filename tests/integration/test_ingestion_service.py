"""Integration test: full ingest_document() flow against the real Postgres container
and a real (tmp_path) local filesystem storage backend.
"""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from testgen.ingestion.service import ingest_document
from testgen.platform.enums import DocumentFormat, RequirementStatus
from testgen.platform.models import Organization, Project
from testgen.platform.storage import LocalFilesystemStorage


def _make_project(db_session: Session) -> Project:
    org = Organization(name="Acme Health")
    db_session.add(org)
    db_session.flush()
    project = Project(organization_id=org.id, name="Infusion Pump Firmware")
    db_session.add(project)
    db_session.flush()
    return project


@pytest.mark.integration
def test_ingest_markdown_document_creates_source_document_and_requirements(
    db_session: Session, tmp_path: Path
) -> None:
    project = _make_project(db_session)
    storage = LocalFilesystemStorage(str(tmp_path))
    raw = (
        b"# Infusion Pump SRS\n\n"
        b"REQ-001: The system shall stop infusion within 500ms of an occlusion alarm.\n\n"
        b"REQ-002: The system shall log every alarm event with a timestamp.\n\n"
        b"This section is background context with no requirement in it."
    )

    document, requirements = ingest_document(
        db_session,
        project_id=project.id,
        filename="infusion-pump-srs.md",
        raw_bytes=raw,
        storage=storage,
    )

    assert document.file_format == DocumentFormat.MARKDOWN
    assert document.version == 1
    assert storage.exists(document.storage_key)
    assert storage.get(document.storage_key) == raw

    assert len(requirements) == 2
    assert {r.external_ref for r in requirements} == {"REQ-001", "REQ-002"}
    assert all(r.status == RequirementStatus.EXTRACTED for r in requirements)
    assert all(r.source_document_id == document.id for r in requirements)


@pytest.mark.integration
def test_reingesting_same_filename_increments_version(db_session: Session, tmp_path: Path) -> None:
    project = _make_project(db_session)
    storage = LocalFilesystemStorage(str(tmp_path))

    doc_v1, _ = ingest_document(
        db_session,
        project_id=project.id,
        filename="srs.md",
        raw_bytes=b"REQ-1: The system shall alarm.",
        storage=storage,
    )
    doc_v2, _ = ingest_document(
        db_session,
        project_id=project.id,
        filename="srs.md",
        raw_bytes=b"REQ-1: The system shall alarm loudly.",
        storage=storage,
    )

    assert doc_v1.version == 1
    assert doc_v2.version == 2
    assert doc_v1.storage_key != doc_v2.storage_key
    assert storage.get(doc_v1.storage_key) != storage.get(doc_v2.storage_key)
