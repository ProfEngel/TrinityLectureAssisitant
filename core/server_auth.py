"""Small dependency-free account store for Trinity's optional server mode."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from pathlib import Path


PBKDF2_ITERATIONS = 310_000
TOKEN_LIFETIME_SECONDS = 12 * 60 * 60


class ServerAuth:
    """Persist password hashes, keep revocable bearer sessions in memory."""

    def __init__(self, home):
        self.path = Path(home).resolve() / "memory" / "server_users.json"
        self._lock = threading.Lock()
        self._tokens = {}

    def status(self):
        with self._lock:
            payload = self._load()
            return {
                "ok": True,
                "enabled": True,
                "configured": bool(payload["users"]),
                "bootstrap_required": not bool(payload["users"]),
                "users": [self.public_user(user) for user in payload["users"]],
            }

    def register_first_admin(self, username, password):
        with self._lock:
            payload = self._load()
            if payload["users"]:
                raise PermissionError("Der erste Server-Account wurde bereits eingerichtet.")
            user = self._create_user(username, password, "admin", payload)
            self._save(payload)
            return self._issue_token(user)

    def login(self, username, password):
        with self._lock:
            payload = self._load()
            user = next(
                (
                    item
                    for item in payload["users"]
                    if item["username"].casefold() == str(username or "").strip().casefold()
                ),
                None,
            )
            if not user or not self._verify_password(user, password):
                raise PermissionError("Benutzername oder Passwort ist nicht korrekt.")
            return self._issue_token(user)

    def create_user(self, actor, username, password, role="user"):
        if not actor or actor.get("role") != "admin":
            raise PermissionError("Nur Administratoren dürfen Accounts anlegen.")
        with self._lock:
            payload = self._load()
            user = self._create_user(username, password, role, payload)
            self._save(payload)
            return self.public_user(user)

    def authenticate(self, token):
        token = str(token or "")
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self._lock:
            session = self._tokens.get(token_hash)
            if not session or session["expires_at"] <= time.time():
                self._tokens.pop(token_hash, None)
                return None
            payload = self._load()
            user = next((item for item in payload["users"] if item["id"] == session["user_id"]), None)
            return self.public_user(user) if user else None

    def _issue_token(self, user):
        token = secrets.token_urlsafe(32)
        self._tokens[hashlib.sha256(token.encode("utf-8")).hexdigest()] = {
            "user_id": user["id"],
            "expires_at": time.time() + TOKEN_LIFETIME_SECONDS,
        }
        return {"token": token, "expires_at": int(time.time() + TOKEN_LIFETIME_SECONDS), "user": self.public_user(user)}

    def _create_user(self, username, password, role, payload):
        username = " ".join(str(username or "").split())
        if len(username) < 2:
            raise ValueError("Benutzername muss mindestens zwei Zeichen haben.")
        if len(str(password or "")) < 10:
            raise ValueError("Passwort muss mindestens zehn Zeichen haben.")
        if any(item["username"].casefold() == username.casefold() for item in payload["users"]):
            raise ValueError("Benutzername existiert bereits.")
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256", str(password).encode("utf-8"), salt, PBKDF2_ITERATIONS
        )
        user = {
            "id": f"user-{uuid.uuid4().hex[:16]}",
            "username": username,
            "role": "admin" if role == "admin" else "user",
            "salt": base64.b64encode(salt).decode("ascii"),
            "password": base64.b64encode(digest).decode("ascii"),
            "created_at": time.time(),
        }
        payload["users"].append(user)
        return user

    @staticmethod
    def public_user(user):
        if not user:
            return None
        return {key: user[key] for key in ("id", "username", "role", "created_at")}

    @staticmethod
    def _verify_password(user, password):
        try:
            salt = base64.b64decode(user["salt"])
            expected = base64.b64decode(user["password"])
        except (KeyError, ValueError):
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", str(password or "").encode("utf-8"), salt, PBKDF2_ITERATIONS
        )
        return hmac.compare_digest(actual, expected)

    def _load(self):
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        users = payload.get("users") if isinstance(payload.get("users"), list) else []
        return {"users": users}

    def _save(self, payload):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)
