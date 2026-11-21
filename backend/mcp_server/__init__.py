"""AI Career Copilot as an MCP server (Phase 8).

An MCP (Model Context Protocol) server lets AI apps such as Claude Desktop call tools in your
program. This one is a thin, READ-ONLY adapter: it never touches your database or Chroma folder.
It only asks your running backend (the FastAPI app) for data over HTTP.

    api_client.py  the HTTP client (standard library only, with a built-in read-only allowlist)
    tools.py       the logic of each tool, as plain Python functions (testable without MCP)
    server.py      registers those functions with the MCP SDK (v2) and runs the server
"""

VERSION = "0.8.0"
