"""Loopback HTTP console that drives both chatbots from a browser window.

Commands travel browser -> automation loop through PromptBus; status updates
travel back over Server-Sent Events.
"""

import json
import queue
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from prompts import EXAMPLE_PROMPTS

STATIC_DIR = Path(__file__).resolve().parent / "console"
# Explicit whitelist instead of a path join: no traversal is possible.
STATIC_FILES = {
    "app.js": "application/javascript; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
}
TOKEN_PLACEHOLDER = "__DEMO_TOKEN__"
MAX_PROMPT_CHARS = 4000
MAX_BODY_BYTES = 64 * 1024

PROMPT = "prompt"
RESET = "reset"
RELAYOUT = "relayout"
SHUTDOWN = "shutdown"

POST_ROUTES = {
    "/api/prompt": PROMPT,
    "/api/reset": RESET,
    "/api/relayout": RELAYOUT,
    "/api/shutdown": SHUTDOWN,
}


class PromptBus:
    """Thread-safe command queue plus a fan-out channel for status events."""

    def __init__(self):
        self._commands = queue.Queue()
        self._subscribers = []
        self._lock = threading.Lock()

    def submit(self, kind: str, text: str = ""):
        self._commands.put({"kind": kind, "text": text})

    def next_command(self, timeout: float = 0.5):
        try:
            return self._commands.get(timeout=timeout)
        except queue.Empty:
            return None

    def subscribe(self) -> "queue.Queue":
        subscriber = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.append(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: "queue.Queue"):
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    def publish(self, target: str, state: str, detail: str = ""):
        event = {"target": target, "state": state, "detail": detail}
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                pass


def _make_handler(console: "ConsoleServer"):
    class ConsoleRequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "LocalChatBotConsole/1.0"

        def log_message(self, format, *args):  # noqa: A002 - signature fixed by the base class
            """Silenced: the demo terminal shows automation progress, not HTTP access lines."""

        # --- helpers ---------------------------------------------------------

        def _send_bytes(self, status, content_type, payload: bytes):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, status, payload):
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self._send_bytes(status, "application/json; charset=utf-8", body)

        def _send_error_json(self, status, message: str):
            self._send_json(status, {"error": message})

        def _authorized(self) -> bool:
            """Loopback-only server with no login, so state-changing calls need a token."""
            if not secrets.compare_digest(self.headers.get("X-Demo-Token", ""), console.token):
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin == console.origin

        def _read_json_body(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None
            if length <= 0:
                return {}
            if length > MAX_BODY_BYTES:
                return None
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None

        # --- routes ----------------------------------------------------------

        def _serve_index(self):
            template = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
            body = template.replace(TOKEN_PLACEHOLDER, console.token).encode("utf-8")
            self._send_bytes(HTTPStatus.OK, "text/html; charset=utf-8", body)

        def _serve_static(self, name: str):
            content_type = STATIC_FILES.get(name)
            if content_type is None:
                self._send_error_json(HTTPStatus.NOT_FOUND, "not found")
                return
            self._send_bytes(HTTPStatus.OK, content_type, (STATIC_DIR / name).read_bytes())

        def _serve_events(self):
            subscriber = console.bus.subscribe()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                while not console.stopping:
                    try:
                        event = subscriber.get(timeout=1.0)
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        continue
                    payload = json.dumps(event, separators=(",", ":"))
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                console.bus.unsubscribe(subscriber)

        # --- verbs -----------------------------------------------------------

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._serve_index()
            elif path.startswith("/static/"):
                self._serve_static(path[len("/static/"):])
            elif path == "/api/examples":
                self._send_json(HTTPStatus.OK, {"examples": list(EXAMPLE_PROMPTS)})
            elif path == "/api/events":
                self._serve_events()
            else:
                self._send_error_json(HTTPStatus.NOT_FOUND, "not found")

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            kind = POST_ROUTES.get(path)
            if kind is None:
                self._send_error_json(HTTPStatus.NOT_FOUND, "not found")
                return
            if not self._authorized():
                self._send_error_json(HTTPStatus.FORBIDDEN, "invalid token or origin")
                return

            body = self._read_json_body()
            if body is None or not isinstance(body, dict):
                self._send_error_json(HTTPStatus.BAD_REQUEST, "invalid request body")
                return

            text = ""
            if kind == PROMPT:
                text = str(body.get("text", "")).strip()
                if not text:
                    self._send_error_json(HTTPStatus.BAD_REQUEST, "prompt is empty")
                    return
                if len(text) > MAX_PROMPT_CHARS:
                    self._send_error_json(
                        HTTPStatus.BAD_REQUEST, f"prompt exceeds {MAX_PROMPT_CHARS} characters"
                    )
                    return

            console.bus.submit(kind, text)
            self._send_json(HTTPStatus.ACCEPTED, {"accepted": kind})

    return ConsoleRequestHandler


class ConsoleServer:
    def __init__(self, bus: PromptBus, host: str = "127.0.0.1", port: int = 8102):
        self.bus = bus
        self.token = secrets.token_urlsafe(32)
        self.stopping = False
        self._httpd = ThreadingHTTPServer((host, port), _make_handler(self))
        self._httpd.daemon_threads = True
        bound_host, bound_port = self._httpd.server_address[:2]
        self.origin = f"http://{bound_host}:{bound_port}"
        self.url = f"{self.origin}/"
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self.stopping = True
        self._httpd.shutdown()
        self._httpd.server_close()
