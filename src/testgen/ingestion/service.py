"""Ingestion's public API: turns an uploaded file into a SourceDocument + candidate Requirements."""

import hashlib
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from testgen.ingestion.models import Requirement, SourceDocument
from testgen.ingestion.parsers import detect_format, extract_text
from testgen.ingestion.requirement_splitter import split_into_candidate_requirements
from testgen.platform.enums import RequirementStatus
from testgen.platform.storage import StoragePort, get_storage


def _next_version(session: Session, project_id: uuid.UUID, filename: str) -> int:
    current_max = session.execute(
        select(func.max(SourceDocument.version)).where(
            SourceDocument.project_id == project_id, SourceDocument.filename == filename
        )
    ).scalar_one()
    return (current_max or 0) + 1


def ingest_document(
    session: Session,
    *,
    project_id: uuid.UUID,
    filename: str,
    raw_bytes: bytes,
    uploaded_by: uuid.UUID | None = None,
    storage: StoragePort | None = None,
) -> tuple[SourceDocument, list[Requirement]]:
    """Parses, stores, and persists one uploaded requirements document.

    Returns the SourceDocument row and the candidate Requirement rows extracted
    from it (status=EXTRACTED — safety classification happens later, in the
    generation phase's Requirement Analyst agent).
    """
    storage = storage or get_storage()
    file_format = detect_format(filename)
    checksum = hashlib.sha256(raw_bytes).hexdigest()
    version = _next_version(session, project_id, filename)
    storage_key = f"{project_id}/{version}/{filename}"

    storage.put(storage_key, raw_bytes)

    document = SourceDocument(
        project_id=project_id,
        filename=filename,
        file_format=file_format,
        checksum=checksum,
        storage_key=storage_key,
        version=version,
        uploaded_by=uploaded_by,
    )
    session.add(document)
    session.flush()

    text = extract_text(file_format, raw_bytes)
    candidates = split_into_candidate_requirements(text)

    requirements = [
        Requirement(
            source_document_id=document.id,
            project_id=project_id,
            external_ref=candidate.external_ref,
            text=candidate.text,
            source_span_start=candidate.span_start,
            source_span_end=candidate.span_end,
            status=RequirementStatus.EXTRACTED,
        )
        for candidate in candidates
    ]
    session.add_all(requirements)
    session.flush()

    return document, requirements
