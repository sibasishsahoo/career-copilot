"""The MCP server as an AI app sees it, using the SDK's own in-memory client.

Needs the MCP SDK (pip install -r requirements-mcp.txt); skipped automatically when it is missing.
The backend is a fake HTTP server, so no real backend, database or API key is involved.
"""

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from mcp import Client  # noqa: E402

from mcp_server.api_client import ApiClient  # noqa: E402
from mcp_server.server import create_server  # noqa: E402
from tests.fake_backend import closed_port_url, fake_backend  # noqa: E402
from tests.test_mcp_tools import DETAIL, LIST_ITEM, RESULTS  # noqa: E402

ROUTES = {
    ("GET", "/applications"): (200, [LIST_ITEM]),
    ("GET", "/applications/7"): (200, DETAIL),
    ("GET", "/applications/999"): (404, {"detail": "Application 999 was not found."}),
    ("POST", "/knowledge/search"): (200, RESULTS),
}


def run_scenario(scenario, routes=ROUTES, url=None):
    """Start a server wired to a fake backend, connect an in-memory client, and run `scenario(client)`."""

    async def runner(base_url):
        async with Client(create_server(ApiClient(base_url))) as client:
            return await scenario(client)

    if url is not None:
        return asyncio.run(runner(url)), None
    with fake_backend(routes) as backend:
        return asyncio.run(runner(backend.url)), backend


def text_of(result) -> str:
    return result.content[0].text


# ======================= discovery =======================

def test_the_server_offers_exactly_the_three_read_tools():
    async def scenario(client):
        return await client.list_tools()

    listed, _ = run_scenario(scenario)
    assert sorted(tool.name for tool in listed.tools) == ["get_application", "list_applications", "search_knowledge"]
    assert all(tool.description for tool in listed.tools)


def test_the_input_schemas_come_from_the_type_hints():
    async def scenario(client):
        return {tool.name: tool.input_schema for tool in (await client.list_tools()).tools}

    schemas, _ = run_scenario(scenario)
    assert set(schemas["list_applications"]["properties"]) == {"status", "search", "limit"}
    assert not schemas["list_applications"].get("required")
    assert schemas["get_application"]["required"] == ["application_id"]
    assert schemas["search_knowledge"]["required"] == ["query"]
    assert set(schemas["search_knowledge"]["properties"]) == {"query", "k", "min_score"}


def test_the_parameter_descriptions_from_the_docstrings_reach_the_model():
    async def scenario(client):
        return {tool.name: tool.input_schema for tool in (await client.list_tools()).tools}

    schemas, _ = run_scenario(scenario)
    assert "wishlist, applied" in schemas["list_applications"]["properties"]["status"].get("description", "")


# ======================= calling tools =======================

def test_list_applications_returns_json_text():
    async def scenario(client):
        return await client.call_tool("list_applications", {})

    result, backend = run_scenario(scenario)
    assert result.is_error is False
    data = json.loads(text_of(result))
    assert data["count"] == 1 and data["applications"][0]["company"] == "Acme"
    assert backend.requests[0].target == "/applications?limit=10"


def test_arguments_are_passed_through_to_the_backend():
    async def scenario(client):
        return await client.call_tool("list_applications", {"status": "applied", "search": "acme", "limit": 3})

    _, backend = run_scenario(scenario)
    target = backend.requests[0].target
    assert "status=applied" in target and "search=acme" in target and "limit=3" in target


def test_get_application_returns_details_history_and_match():
    async def scenario(client):
        return await client.call_tool("get_application", {"application_id": 7})

    result, _ = run_scenario(scenario)
    data = json.loads(text_of(result))
    assert data["company"] == "Acme" and data["saved_match"]["score"] == 72
    assert [h["to"] for h in data["status_history"]] == ["wishlist", "applied"]


def test_search_knowledge_posts_to_the_notes_search():
    async def scenario(client):
        return await client.call_tool("search_knowledge", {"query": "deployment time"})

    result, backend = run_scenario(scenario)
    assert json.loads(text_of(result))["matches"][0]["note"] == "Faster deployments"
    assert backend.requests[0].method == "POST"
    assert backend.requests[0].body == {"query": "deployment time", "k": 3}


# ======================= errors reach the model as readable error results =======================

def test_invalid_arguments_come_back_as_an_error_result_not_a_crash():
    async def scenario(client):
        return await client.call_tool("list_applications", {"status": "ghosted"})

    result, backend = run_scenario(scenario)
    assert result.is_error is True
    assert "must be one of" in text_of(result)
    assert backend.requests == []


def test_a_missing_application_is_an_error_result_with_the_backends_message():
    async def scenario(client):
        return await client.call_tool("get_application", {"application_id": 999})

    result, _ = run_scenario(scenario)
    assert result.is_error is True
    assert "Application 999 was not found." in text_of(result)


def test_a_backend_that_is_not_running_says_how_to_start_it():
    async def scenario(client):
        return await client.call_tool("list_applications", {})

    result, _ = run_scenario(scenario, url=closed_port_url())
    assert result.is_error is True
    assert "Cannot reach the Career Copilot backend" in text_of(result)


# ======================= resources =======================

def test_the_applications_resource_lists_applications():
    async def scenario(client):
        return await client.read_resource("career://applications")

    result, _ = run_scenario(scenario)
    assert json.loads(result.contents[0].text)["count"] == 1


def test_the_application_resource_template_reads_one_application():
    async def scenario(client):
        return await client.read_resource("career://applications/7")

    result, backend = run_scenario(scenario)
    assert json.loads(result.contents[0].text)["company"] == "Acme"
    assert backend.requests[0].target == "/applications/7"


def test_an_unknown_application_resource_is_an_error():
    async def scenario(client):
        return await client.read_resource("career://applications/999")

    with pytest.raises(ExceptionGroup) as exc_info:
        run_scenario(scenario)

    assert "999" in repr(exc_info.value)


# ======================= prompts =======================

def test_the_interview_prompt_is_offered_and_filled_in():
    async def scenario(client):
        return await client.get_prompt("prepare_for_interview", {"application_id": "7", "focus": "system design"})

    result, backend = run_scenario(scenario)
    message = result.messages[0]
    assert message.role == "user"
    assert "application_id 7" in message.content.text and "system design" in message.content.text
    assert backend.requests == []  # building a prompt does not touch the backend


# ======================= read-only, seen from outside =======================

def test_nothing_a_client_can_do_causes_a_write_request():
    async def scenario(client):
        await client.list_tools()
        await client.call_tool("list_applications", {})
        await client.call_tool("get_application", {"application_id": 7})
        await client.call_tool("search_knowledge", {"query": "x"})
        await client.read_resource("career://applications")
        await client.read_resource("career://applications/7")
        # attempts the model might make
        for name in ("create_application", "delete_application", "update_application", "change_status"):
            try:
                await client.call_tool(name, {"id": 7})
            except Exception:
                pass

    _, backend = run_scenario(scenario)
    allowed = {("GET", "/applications"), ("GET", "/applications/7"), ("POST", "/knowledge/search")}
    assert {(r.method, r.target.split("?")[0]) for r in backend.requests} <= allowed
