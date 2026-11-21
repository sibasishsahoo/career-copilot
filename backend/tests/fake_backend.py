"""A real HTTP server on localhost that plays the Career Copilot backend, for tests.

routes: {(METHOD, "/path"): (status, body)} or (status, body, {"headers": {...}, "delay": seconds})
  body: dict/list -> sent as JSON; str -> sent as is; None -> empty
Every request that arrives is recorded in `.requests`, including ones the test expects NOT to arrive.
"""

import json
import socket
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


@dataclass
class Recorded:
    method: str
    target: str  # path + query string, exactly as received
    content_type: str | None
    accept: str | None
    body: object  # parsed JSON, or None


@dataclass
class FakeBackend:
    url: str
    requests: list


def closed_port_url() -> str:
    """A localhost URL where nothing is listening (connection refused)."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"


@contextmanager
def fake_backend(routes: dict):
    requests: list[Recorded] = []

    class Handler(BaseHTTPRequestHandler):
        def _handle(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            requests.append(
                Recorded(method, self.path, self.headers.get("Content-Type"), self.headers.get("Accept"),
                         json.loads(raw) if raw else None)
            )
            route = routes.get((method, urlsplit(self.path).path))
            if route is None:
                route = (404, {"detail": "Not Found"})
            status, body, *rest = route
            options = rest[0] if rest else {}
            time.sleep(options.get("delay", 0))

            if isinstance(body, (dict, list)):
                payload = json.dumps(body).encode()
            elif isinstance(body, str):
                payload = body.encode()
            else:
                payload = b""
            try:
                self.send_response(status)
                for name, value in options.get("headers", {}).items():
                    self.send_header(name, value)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass  # the client gave up (for example on a timeout); that is fine

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_PUT(self):
            self._handle("PUT")

        def do_PATCH(self):
            self._handle("PATCH")

        def do_DELETE(self):
            self._handle("DELETE")

        def log_message(self, *args):
            pass  # keep test output quiet

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield FakeBackend(f"http://127.0.0.1:{server.server_address[1]}", requests)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
