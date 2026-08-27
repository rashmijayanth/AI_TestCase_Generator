"""Upload a source document; ingestion runs synchronously (parsing is fast and
deterministic) producing candidate Requirement rows. Generating test cases for
those requirements is a separate, asynchronous step (see requirements router).
"""

import uuid

from fastapi import APIRouter, HTTPException, UploadFile, status

from testgen.api.deps import CurrentUser, DbSession
from testgen.ingestion.service import ingest_document
from testgen.platform.models import Project

router = APIRouter(prefix="/api/v1/projects/{project_id}/documents", tags=["documents"])


def get_owned_project(db: DbSession, user: CurrentUser, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    project_id: uuid.UUID, file: UploadFile, user: CurrentUser, db: DbSession
) -> dict[str, object]:
    project = get_owned_project(db, user, project_id)
    raw_bytes = await file.read()

    try:
        document, requirements = ingest_document(
            db,
            project_id=project.id,
            filename=file.filename or "unnamed",
            raw_bytes=raw_bytes,
            uploaded_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    db.commit()
    return {
        "document_id": str(document.id),
        "filename": document.filename,
        "version": document.version,
        "requirements_extracted": len(requirements),
        "requirement_ids": [str(r.id) for r in requirements],
    }
