"""Talk to the MCP server the way Claude Desktop does: start it as a subprocess and speak MCP over stdio.

First start the BACKEND (the MCP server only fetches data from it):
    uvicorn app.main:app

Then, from the backend folder, in an environment where the MCP SDK is installed:
    python -m scripts.mcp_client_demo
    python -m scripts.mcp_client_demo --application 3       # also show application 3 and its interview prompt
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

BACKEND_DIR = Path(__file__).resolve().parents[1]


def shorten(text: str, limit: int = 400) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


async def main(application_id: str | None) -> int:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(BACKEND_DIR / "run_mcp_server.py")],
        env={**os.environ},  # includes CAREER_COPILOT_API_URL if you set it
    )
    async with Client(parameters) as client:
        print("TOOLS")
        for tool in (await client.list_tools()).tools:
            print(f"  {tool.name}: {shorten((tool.description or '').splitlines()[0], 90)}")

        print("\nlist_applications(limit=5)")
        result = await client.call_tool("list_applications", {"limit": 5})
        print(f"  is_error={result.is_error}\n  {shorten(result.content[0].text)}")

        print("\nsearch_knowledge('leadership')")
        result = await client.call_tool("search_knowledge", {"query": "leadership"})
        print(f"  is_error={result.is_error}\n  {shorten(result.content[0].text)}")

        if application_id:
            print(f"\nget_application({application_id})")
            result = await client.call_tool("get_application", {"application_id": int(application_id)})
            print(f"  is_error={result.is_error}\n  {shorten(result.content[0].text)}")

            print("\nprompt prepare_for_interview")
            prompt = await client.get_prompt("prepare_for_interview", {"application_id": application_id})
            print("  " + shorten(prompt.messages[0].content.text, 300).replace("\n", "\n  "))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Try the Career Copilot MCP server over stdio.")
    parser.add_argument("--application", help="an application id to look at in detail")
    sys.exit(asyncio.run(main(parser.parse_args().application)))
