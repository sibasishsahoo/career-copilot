"""The MCP tools and the Phase 7 agent tools must stay in step: same names, same limits, same results.

Runs in your normal backend environment (it imports the agent's tools, which use SQLAlchemy).
"""

import json

from app.models.application import ApplicationStatus
from app.schemas.application import ApplicationCreate, ApplicationDetail, MatchSnapshotCreate, StatusChangeCreate
from app.services import application_service as tracker
from app.services.agent.knowledge_tools import build_search_knowledge_tool
from app.services.agent.tools import execute_tool, ToolRegistry
from app.services.agent.tracker_tools import build_get_application_tool, build_list_applications_tool
from mcp_server import tools as mcp_tools


def agent_tools():
    return {
        tool.name: tool
        for tool in (
            build_list_applications_tool(None),
            build_get_application_tool(None),
            build_search_knowledge_tool(lambda: None, None),
        )
    }


def param(tool, name):
    return next(p for p in tool.params if p.name == name)


def normalize(value):
    """The API writes UTC as '...Z', the agent as '...+00:00'. Same instant: compare them as equal."""
    if isinstance(value, str) and value.endswith("Z"):
        return value[:-1] + "+00:00"
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    return value


# ======================= the limits agree =======================

def test_the_status_choices_match_the_trackers_statuses():
    assert mcp_tools.STATUSES == tuple(status.value for status in ApplicationStatus)


def test_list_applications_limits_match_the_agent_tool():
    tool = agent_tools()["list_applications"]
    assert param(tool, "status").enum == mcp_tools.STATUSES
    assert param(tool, "search").max_length == mcp_tools.SEARCH_MAX_CHARS
    limit = param(tool, "limit")
    assert (limit.default, limit.minimum, limit.maximum) == (mcp_tools.LIMIT_DEFAULT, mcp_tools.LIMIT_MIN, mcp_tools.LIMIT_MAX)


def test_search_knowledge_limits_match_the_agent_tool():
    tool = agent_tools()["search_knowledge"]
    assert param(tool, "query").max_length == mcp_tools.QUERY_MAX_CHARS
    k = param(tool, "k")
    assert (k.default, k.minimum, k.maximum) == (mcp_tools.K_DEFAULT, mcp_tools.K_MIN, mcp_tools.K_MAX)


def test_get_application_takes_a_positive_integer_id_in_both():
    assert param(agent_tools()["get_application"], "id").minimum == 1


def test_both_expose_the_same_tool_names():
    assert sorted(agent_tools()) == ["get_application", "list_applications", "search_knowledge"]


# ======================= the results agree =======================

class RestStandIn:
    """Feeds the MCP tools the SAME JSON the real REST API would produce for the same database rows."""

    def __init__(self, db, application_id):
        detail = ApplicationDetail.model_validate(tracker.get_application(db, application_id))
        self.detail = detail.model_dump(mode="json")
        self.summary = {k: v for k, v in self.detail.items() if k not in ("status_history", "match_snapshot")}

    def get(self, path, params=None):
        return [self.summary] if path == "/applications" else self.detail


def seed(db):
    application = tracker.create_application(
        db, ApplicationCreate(company="Acme", job_title="Backend Engineer", location="Remote",
                              job_url="https://example.com/1", notes="Referred by Sam"),
    )
    tracker.change_status(db, application.id, StatusChangeCreate(status="applied", note="Applied online"))
    tracker.attach_match(db, application.id, MatchSnapshotCreate(
        job_description="We need Python and SQL.", score=72,
        matched_skills=[{"skill": "Python", "category": "required"}],
        missing_skills=[{"skill": "Docker", "category": "preferred"}],
    ))
    return application


def test_get_application_results_are_identical(db):
    application = seed(db)
    registry = ToolRegistry([build_get_application_tool(db)])
    from_agent = json.loads(execute_tool(registry, "get_application", {"id": application.id}).observation)
    from_mcp = mcp_tools.get_application(RestStandIn(db, application.id), application.id)
    assert normalize(from_mcp) == normalize(from_agent)


def test_list_applications_results_are_identical(db):
    application = seed(db)
    registry = ToolRegistry([build_list_applications_tool(db)])
    from_agent = json.loads(execute_tool(registry, "list_applications", {}).observation)
    from_mcp = mcp_tools.list_applications(RestStandIn(db, application.id))
    assert normalize(from_mcp) == normalize(from_agent)
