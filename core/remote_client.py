"""HTTP client used by a Trinity desktop installation in client role."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class RemoteTrinityClient:
    def __init__(self, server_url, token="", timeout=12):
        self.server_url = str(server_url or "").rstrip("/")
        self.token = str(token or "")
        self.timeout = timeout
        if not self.server_url.startswith(("http://", "https://")):
            raise ValueError("Server-URL muss mit http:// oder https:// beginnen.")

    def login(self, username, password, register=False):
        result = self._request(
            "/auth/register" if register else "/auth/login",
            {"username": username, "password": password},
            authenticated=False,
        )
        self.token = str(result.get("token") or "")
        if not self.token:
            raise RuntimeError("Server hat kein Sitzungstoken geliefert.")
        return result

    def auth_status(self):
        return self._request("/auth/status", authenticated=False, method="GET")

    def send_message(self, text, attachments=None, source="classic", speak=False, session_id="", session_name=""):
        payload = {
            "text": text,
            "attachments": self.encode_attachments(attachments or []),
            "source": source,
            "speak": bool(speak),
            "session_id": session_id,
            "session_name": session_name,
        }
        return self._request("/message", payload)

    def events_since(self, after=0.0, session_id=""):
        query = {"after": float(after)}
        if str(session_id or "").strip():
            query["session_id"] = str(session_id).strip()
        return self._request(f"/events?{urlencode(query)}", method="GET").get("events", [])

    def latest_payload(self):
        return self._request("/payload", method="GET")

    def get_runtime(self):
        return self._request("/runtime", method="GET")

    def set_runtime(self, updates):
        return self._request("/runtime", dict(updates or {}))

    def end_session(self, payload):
        return self._request("/session/end", dict(payload or {}))

    def create_user(self, username, password, role="user"):
        return self._request(
            "/auth/users",
            {"username": username, "password": password, "role": role},
        )

    @staticmethod
    def encode_attachments(attachments):
        encoded = []
        for item in attachments:
            path = Path(str(item.get("path") or ""))
            if not path.is_file():
                continue
            encoded.append(
                {
                    "name": item.get("name") or path.name,
                    "mime": item.get("mime") or "application/octet-stream",
                    "kind": item.get("kind"),
                    "data_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
                }
            )
        return encoded

    def _request(self, path, payload=None, authenticated=True, method="POST"):
        url = self.server_url + path
        data = None
        headers = {"Accept": "application/json"}
        if authenticated:
            if not self.token:
                raise RuntimeError("Bitte zuerst mit `trinity client login` anmelden.")
            headers["Authorization"] = f"Bearer {self.token}"
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(body).get("error", body)
            except json.JSONDecodeError:
                message = body
            raise RuntimeError(f"Server antwortet mit HTTP {exc.code}: {message}") from exc
        except URLError as exc:
            raise RuntimeError(f"Server nicht erreichbar: {exc.reason}") from exc
        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Server lieferte keine gültige JSON-Antwort.") from exc
        if not result.get("ok", False):
            raise RuntimeError(str(result.get("error") or "Server-Anfrage fehlgeschlagen."))
        return result
