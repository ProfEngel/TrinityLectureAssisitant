"""Small HTTP bridge for Trinity companion clients on a trusted tailnet."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from chat_protocol import append_chat_event, build_chat_request, encode_chat_request, load_chat_events


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BODY_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 200


def _json_response(handler, status, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(data)


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length > MAX_BODY_BYTES:
        raise ValueError("Request ist zu groß.")
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _is_relative_to(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


class TrinityBridge:
    def __init__(self, home, token=""):
        self.home = Path(home).resolve()
        self.core_dir = self.home / "core"
        self.memory_dir = self.home / "memory"
        self.history_path = self.memory_dir / "classic_chat_history.jsonl"
        self.command_path = self.core_dir / "cmd.txt"
        self.payload_path = self.core_dir / "payload.html"
        self.token = token or ""
        self._lock = threading.Lock()

    @property
    def media_roots(self):
        return [
            self.home / "gen_images",
            self.home / "agents" / "comfyui_agent" / "media",
            self.home / "memory",
        ]

    def check_auth(self, handler):
        if not self.token:
            return True
        header = handler.headers.get("Authorization", "")
        return header == f"Bearer {self.token}"

    def send_message(self, payload):
        text = str(payload.get("text", "")).strip()
        if not text:
            raise ValueError("Text darf nicht leer sein.")

        request = build_chat_request(text, [], history_recorded=True)
        request["source"] = "ios"
        request["session_id"] = str(payload.get("session_id", "")).strip()
        request["privacy_mode"] = str(payload.get("privacy_mode", "local")).strip() or "local"

        with self._lock:
            if self.command_path.exists():
                raise RuntimeError("Trinity verarbeitet noch eine vorherige Anfrage.")
            append_chat_event(
                self.history_path,
                {
                    "request_id": request["request_id"],
                    "role": "user",
                    "source": "ios",
                    "text": text,
                    "attachments": [],
                    "session_id": request["session_id"],
                    "privacy_mode": request["privacy_mode"],
                },
            )
            self.command_path.write_text(encode_chat_request(request), encoding="utf-8")

        return {"ok": True, "request_id": request["request_id"], "accepted_at": time.time()}

    def events_since(self, after=0.0, limit=MAX_EVENTS):
        events = []
        for event in load_chat_events(self.history_path, limit=max(limit * 3, MAX_EVENTS)):
            timestamp = float(event.get("timestamp", 0) or 0)
            if timestamp <= after:
                continue
            cleaned = dict(event)
            if cleaned.get("payload_html"):
                cleaned["payload_html"] = self.rewrite_html(cleaned["payload_html"])
            events.append(cleaned)
        return events[-limit:]

    def latest_payload(self):
        try:
            html = self.payload_path.read_text(encoding="utf-8")
        except OSError:
            html = ""
        return {"html": self.rewrite_html(html), "timestamp": self._mtime(self.payload_path)}

    def media_path_from_query(self, raw_path):
        if not raw_path:
            raise ValueError("Kein Medienpfad angegeben.")
        value = unquote(raw_path)
        if value.startswith("file://"):
            value = urlparse(value).path
        path = Path(value).expanduser().resolve()
        for root in self.media_roots:
            if _is_relative_to(path, root):
                if path.is_file():
                    return path
                raise FileNotFoundError(path)
        raise PermissionError("Medienpfad ist nicht freigegeben.")

    def rewrite_html(self, html):
        if not html:
            return ""

        def replace(match):
            quote_char = match.group(1)
            url = match.group(2)
            parsed = urlparse(url)
            path = parsed.path if parsed.scheme == "file" else url
            return f"{quote_char}/media?path={quote(path)}{quote_char}"

        return re.sub(r"(['\"])(file://[^'\"]+)\1", replace, html)

    @staticmethod
    def _mtime(path):
        try:
            return Path(path).stat().st_mtime
        except OSError:
            return 0.0


def make_handler(bridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = "TrinityBridge/0.1"

        def log_message(self, fmt, *args):
            print(f"[bridge] {self.address_string()} - {fmt % args}")

        def do_OPTIONS(self):  # noqa: N802
            _json_response(self, 200, {"ok": True})

        def do_GET(self):  # noqa: N802
            if not bridge.check_auth(self):
                _json_response(self, 401, {"ok": False, "error": "unauthorized"})
                return
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path == "/health":
                    _json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "name": "Trinity Bridge",
                            "time": time.time(),
                            "history": bridge.history_path.exists(),
                        },
                    )
                elif parsed.path == "/events":
                    after = float(query.get("after", ["0"])[0] or 0)
                    _json_response(self, 200, {"ok": True, "events": bridge.events_since(after)})
                elif parsed.path == "/payload":
                    _json_response(self, 200, {"ok": True, **bridge.latest_payload()})
                elif parsed.path == "/media":
                    path = bridge.media_path_from_query(query.get("path", [""])[0])
                    data = path.read_bytes()
                    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                else:
                    _json_response(self, 404, {"ok": False, "error": "not found"})
            except Exception as exc:  # pylint: disable=broad-except
                _json_response(self, 400, {"ok": False, "error": str(exc)})

        def do_POST(self):  # noqa: N802
            if not bridge.check_auth(self):
                _json_response(self, 401, {"ok": False, "error": "unauthorized"})
                return
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/message":
                    _json_response(self, 200, bridge.send_message(_read_json(self)))
                else:
                    _json_response(self, 404, {"ok": False, "error": "not found"})
            except RuntimeError as exc:
                _json_response(self, 409, {"ok": False, "error": str(exc)})
            except Exception as exc:  # pylint: disable=broad-except
                _json_response(self, 400, {"ok": False, "error": str(exc)})

    return Handler


def run_bridge(home, host=DEFAULT_HOST, port=DEFAULT_PORT, token=""):
    bridge = TrinityBridge(home, token=token)
    server = ThreadingHTTPServer((host, int(port)), make_handler(bridge))
    print(f"Trinity Bridge läuft auf http://{host}:{port}")
    if host in {"0.0.0.0", "::"}:
        print("Hinweis: Für Tailscale erreichbar. Nutze wenn möglich --token.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTrinity Bridge beendet.")
    finally:
        server.server_close()
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Trinity HTTP Bridge starten.")
    parser.add_argument("--home", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--token", default=os.environ.get("TRINITY_BRIDGE_TOKEN", ""))
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return run_bridge(args.home, host=args.host, port=args.port, token=args.token)


if __name__ == "__main__":
    raise SystemExit(main())
