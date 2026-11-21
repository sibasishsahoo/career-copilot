"""The MCP server: registers the tool functions from tools.py with the official MCP Python SDK (v2).

MCP lets an AI app discover and use three kinds of things your server offers:
    TOOLS      functions the model can call          (list_applications, get_application, search_knowledge)
    RESOURCES  data the app can read or attach       (career://applications, career://applications/{id})
    PROMPTS    reusable templates the USER can pick  (prepare_for_interview)

IMPORTANT for stdio servers: the protocol travels over stdin/stdout, so NEVER print() anything.
Logging goes to stderr (see main()).
"""

import logging
import sys
from collections.abc import Callable
from typing import Any
from typing import Annotated, Any
from pydantic import Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ResourceNotFoundError, ToolError

from mcp_server import VERSION, tools
from mcp_server.api_client import ApiClient, BackendError

SERVER_NAME = "career-copilot"
INSTRUCTIONS = (
    "Read-only access to the user's job application tracker and personal career notes. "
    "Use list_applications to find an application's id, get_application for its full details and "
    "saved job match, and search_knowledge to find the user's own stories and achievements. "
    "These tools cannot change anything."
)


def _tool_result(action: Callable[[], Any]) -> str:
    """Run a tool. Expected failures become a ToolError, which MCP delivers to the model as an error
    RESULT (is_error=true) that it can read and react to, instead of a protocol-level crash."""
    try:
        return tools.render(action())
    except (tools.ToolInputError, BackendError) as exc:
        raise ToolError(str(exc)) from exc


def _resource_result(action: Callable[[], Any]) -> str:
    try:
        return tools.render(action())
    except tools.ToolInputError as exc:
        raise ResourceNotFoundError(str(exc)) from exc
    except BackendError as exc:
        if exc.status == 404:
            raise ResourceNotFoundError(str(exc)) from exc
        raise ResourceError(str(exc)) from exc


def create_server(api: ApiClient) -> MCPServer:
    """Build the server around a given backend client (tests pass one that points at a fake backend)."""
    mcp = MCPServer(SERVER_NAME, instructions=INSTRUCTIONS, version=VERSION)

    # ------------------------------------------------------------------ tools
    # The function name becomes the tool name, the type hints become its input schema, and the
    # docstring becomes its description (including the "Args:" part, one line per parameter).

    @mcp.tool()
    def list_applications(
        status: Annotated[
    str | None,
    Field(
        description="Only applications in this status:wishlist, applied, interviewing, withdrawn"
    ),
        ] = None,
        search: str | None = None,
        limit: int = tools.LIMIT_DEFAULT,
    ) -> str:
        """List the user's job applications, most recently updated first.

        Each entry has id, company, job_title, status, location, applied_date and updated_at.
 
        
        Args:
            status: only applications in this status: wishlist, applied, interviewing, offer, rejected or withdrawn
            search: text to look for in the company or job title
            limit: maximum number of applications to return, from 1 to 25
        """
        return _tool_result(lambda: tools.list_applications(api, status, search, limit))

    @mcp.tool()
    def get_application(application_id: int) -> str:
        """Get everything about ONE application: its details, its full status history, and the saved
        job match (score, matched and missing skills) if there is one.

        Args:
            application_id: the application's id, as shown by list_applications
        """
        return _tool_result(lambda: tools.get_application(api, application_id))

    @mcp.tool()
    def search_knowledge(query: str, k: int = tools.K_DEFAULT, min_score: float = 0.0) -> str:
        """Search the user's own career notes (project write-ups, STAR stories, achievements) by meaning.

        Returns the best matching passages with their note titles and a similarity score. A higher score
        means a better match; very low scores usually mean the note is unrelated.

        Args:
            query: what to look for, in plain words
            k: how many passages to return, from 1 to 5
            min_score: ignore passages scoring below this (0 to 1); the default 0 keeps everything
        """
        return _tool_result(lambda: tools.search_knowledge(api, query, k, min_score))

    # ------------------------------------------------------------------ resources
    # A resource is read by URI. "{application_id}" in the URI makes it a TEMPLATE: the value in the
    # URI is passed to the function as a string.

    @mcp.resource("career://applications", mime_type="application/json")
    def applications_resource() -> str:
        """All of the user's applications (up to 25), most recently updated first."""
        return _resource_result(lambda: tools.list_applications(api, None, None, tools.LIMIT_MAX))

    @mcp.resource("career://applications/{application_id}", mime_type="application/json")
    def application_resource(application_id: str) -> str:
        """One application with its status history and saved job match."""
        return _resource_result(lambda: tools.get_application(api, application_id))

    # ------------------------------------------------------------------ prompts

    @mcp.prompt()
    def prepare_for_interview(application_id: str, focus: str = "") -> str:
        """Plan interview preparation for one application, using the user's own tracker data and notes.

        Args:
            application_id: the application's id, as shown by list_applications
            focus: optional topic to concentrate on, for example "system design" or "leadership"
        """
        try:
            return tools.build_interview_prompt(application_id, focus)
        except tools.ToolInputError as exc:
            raise ValueError(str(exc)) from exc

    return mcp


# One server for the whole process. A module-level object named `mcp` is also what `mcp dev` expects.
mcp = create_server(ApiClient.from_env())


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,  # never stdout: stdout carries the protocol
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger(__name__).info("career-copilot MCP server starting (backend: %s)", ApiClient.from_env().base_url)
    mcp.run(transport="stdio")
