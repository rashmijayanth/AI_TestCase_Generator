"""Project CRUD, scoped to the authenticated user's organization."""

from fastapi import APIRouter, status
from sqlalchemy import select

from testgen.api.deps import CurrentUser, DbSession
from testgen.api.schemas import ProjectCreateRequest, ProjectOut
from testgen.platform.models import Project

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreateRequest, user: CurrentUser, db: DbSession) -> ProjectOut:
    project = Project(
        organization_id=user.organization_id, name=payload.name, description=payload.description
    )
    db.add(project)
    db.commit()
    return ProjectOut(id=str(project.id), name=project.name, description=project.description)


@router.get("", response_model=list[ProjectOut])
def list_projects(user: CurrentUser, db: DbSession) -> list[ProjectOut]:
    projects = (
        db.execute(select(Project).where(Project.organization_id == user.organization_id))
        .scalars()
        .all()
    )
    return [ProjectOut(id=str(p.id), name=p.name, description=p.description) for p in projects]
