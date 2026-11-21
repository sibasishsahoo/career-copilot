from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationRead,
    ApplicationStatus,
    ApplicationUpdate,
    MatchSnapshotCreate,
    MatchSnapshotRead,
    StatusChangeCreate,
)
from app.services import application_service as service

router = APIRouter(prefix="/applications", tags=["applications"])

# NOTE: every route converts the ORM object to a Pydantic model INSIDE the function, while
# the database session is still open. Reading related rows (history, snapshot) triggers
# lazy loading, which needs an open session.


@router.post("", response_model=ApplicationDetail, status_code=201)
def create_application(body: ApplicationCreate, db: Session = Depends(get_db)) -> ApplicationDetail:
    return ApplicationDetail.model_validate(service.create_application(db, body))


@router.get("", response_model=list[ApplicationRead])
def list_applications(
    status: ApplicationStatus | None = None,
    search: str | None = Query(default=None, max_length=100, description="Matches company or job title"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ApplicationRead]:
    applications = service.list_applications(db, status=status, search=search, limit=limit, offset=offset)
    return [ApplicationRead.model_validate(application) for application in applications]


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: int, db: Session = Depends(get_db)) -> ApplicationDetail:
    return ApplicationDetail.model_validate(service.get_application(db, application_id))


@router.patch("/{application_id}", response_model=ApplicationDetail)
def update_application(
    application_id: int, body: ApplicationUpdate, db: Session = Depends(get_db)
) -> ApplicationDetail:
    return ApplicationDetail.model_validate(service.update_application(db, application_id, body))


@router.delete("/{application_id}", status_code=204, response_class=Response)
def delete_application(application_id: int, db: Session = Depends(get_db)) -> Response:
    service.delete_application(db, application_id)
    return Response(status_code=204)


@router.post("/{application_id}/status", response_model=ApplicationDetail)
def change_status(
    application_id: int, body: StatusChangeCreate, db: Session = Depends(get_db)
) -> ApplicationDetail:
    """Move an application to another status. The change is recorded in its history."""
    return ApplicationDetail.model_validate(service.change_status(db, application_id, body))


@router.put("/{application_id}/match", response_model=MatchSnapshotRead)
def attach_match(
    application_id: int, body: MatchSnapshotCreate, db: Session = Depends(get_db)
) -> MatchSnapshotRead:
    """Attach (or replace) the match snapshot. The resume itself is never accepted or stored."""
    return MatchSnapshotRead.model_validate(service.attach_match(db, application_id, body))


@router.delete("/{application_id}/match", status_code=204, response_class=Response)
def remove_match(application_id: int, db: Session = Depends(get_db)) -> Response:
    service.remove_match(db, application_id)
    return Response(status_code=204)
