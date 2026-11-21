"""Start the MCP server. Works from any folder, which is what Claude Desktop needs:

    /full/path/to/python /full/path/to/backend/run_mcp_server.py

(From the backend folder you can also run:  python -m mcp_server)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # so "import mcp_server" works from anywhere

from mcp_server.server import main  # noqa: E402

main()
