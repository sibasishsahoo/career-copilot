"""The agent's window onto your job application tracker (Phase 4). READ-ONLY.

These tools call the same service functions the HTTP endpoints use, but only the ones that read.
There is deliberately no tool that creates, changes or deletes anything.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationStatus
from app.services import application_service as tracker
from app.services.agent.tools import Tool, ToolError, ToolParam

_STATUSES = tuple(status.value for status in ApplicationStatus)


def _excerpt(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= limit else text[:limit] + "..."


def _summary(application: Application) -> dict[str, Any]:
    return {
        "id": application.id,
        "company": application.company,
        "job_title": application.job_title,
        "status": application.status,
        "location": application.location,
        "applied_date": application.applied_date.isoformat() if application.applied_date else None,
        "updated_at": application.updated_at.isoformat(),
    }


def build_list_applications_tool(db: Session) -> Tool:
    def run(args: dict[str, Any]) -> dict[str, Any]:
        status = ApplicationStatus(args["status"]) if "status" in args else None
        applications = tracker.list_applications(
            db, status=status, search=args.get("search") or None, limit=args["limit"]
        )
        return {"count": len(applications), "applications": [_summary(a) for a in applications]}

    return Tool(
        name="list_applications",
        description=(
            "List the user's job applications, most recently updated first. "
            "Each entry has id, company, job_title, status, location, applied_date and updated_at."
        ),
        params=(
            ToolParam("status", "string", "only applications in this status", required=False, enum=_STATUSES),
            ToolParam("search", "string", "text to look for in company or job title", required=False, max_length=100),
            ToolParam("limit", "integer", "maximum number of applications", required=False, default=10, minimum=1, maximum=25),
        ),
        run=run,
    )


def build_get_application_tool(db: Session) -> Tool:
    def run(args: dict[str, Any]) -> dict[str, Any]:
        try:
            application = tracker.get_application(db, args["id"])
        except tracker.TrackerNotFoundError as exc:
            raise ToolError(str(exc)) from exc

        snapshot = application.match_snapshot
        saved_match = None
        if snapshot is not None:
            saved_match = {
                "score": snapshot.score,
                "matched_skills": snapshot.matched_skills,
                "missing_skills": snapshot.missing_skills,
                "job_description_excerpt": _excerpt(snapshot.job_description, 600),
            }

        return {
            **_summary(application),
            "job_url": application.job_url,
            "notes": _excerpt(application.notes, 800),
            "status_history": [
                {
                    "from": change.from_status,
                    "to": change.to_status,
                    "note": change.note,
                    "at": change.changed_at.isoformat(),
                }
                for change in application.status_history
            ],
            "saved_match": saved_match,
        }

    return Tool(
        name="get_application",
        description=(
            "Get everything about ONE application: its details, its full status history, and the "
            "saved job-match (score, matched and missing skills) if there is one."
        ),
        params=(ToolParam("id", "integer", "the application id, as shown by list_applications", minimum=1),),
        run=run,
    )
