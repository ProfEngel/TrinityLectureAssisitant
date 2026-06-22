"""Local, one-time approvals with optional parent/child scopes."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Optional


class ApprovalManager:
    """Persist approvals locally; a decision is bound to one job and one action."""

    def __init__(self, home: Optional[str | Path] = None):
        root = Path(home or Path(__file__).resolve().parents[1]).resolve()
        memory = root / "memory"
        memory.mkdir(parents=True, exist_ok=True)
        self.db_path = memory / "approvals.sqlite3"
        self.secret_path = memory / ".approval_secret"
        self._secret = self._load_secret()
        self._init_db()

    def request(
        self,
        job_id: str,
        action_type: str,
        summary: str,
        risk_level: str = "medium",
        details: Optional[dict] = None,
        expires_in_seconds: int = 900,
        parent_approval_id: str = "",
    ) -> dict:
        if not job_id:
            raise ValueError("Freigabe braucht einen Job.")
        action = str(action_type).strip()
        if not action:
            raise ValueError("Freigabe braucht einen Aktionstyp.")
        parent = str(parent_approval_id or "").strip()
        if parent:
            self._validate_parent(parent, job_id, action)
        approval_id = f"approval_{uuid.uuid4().hex}"
        now = time.time()
        expires_at = now + max(60, min(int(expires_in_seconds), 86_400))
        token = self._sign(approval_id, job_id, action, expires_at)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO approvals (
                    approval_id, job_id, parent_approval_id, action_type, risk_level,
                    summary, details_json, status, created_at, expires_at, token_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?)
                """,
                (
                    approval_id,
                    job_id,
                    parent,
                    action,
                    str(risk_level or "medium"),
                    str(summary or action),
                    json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
                    now,
                    expires_at,
                    hashlib.sha256(token.encode("utf-8")).hexdigest(),
                ),
            )
        return self.get(approval_id, include_token=token)

    def get(self, approval_id: str, include_token: str = "") -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"Freigabe nicht gefunden: {approval_id}")
        result = {
            "approval_id": row["approval_id"],
            "job_id": row["job_id"],
            "parent_approval_id": row["parent_approval_id"],
            "action_type": row["action_type"],
            "risk_level": row["risk_level"],
            "summary": row["summary"],
            "details": _load(row["details_json"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "decided_at": row["decided_at"],
            "decided_by": row["decided_by"],
            "used_at": row["used_at"],
        }
        if include_token:
            result["token"] = include_token
        return result

    def list_pending(self, job_id: str = "") -> list[dict]:
        query = "SELECT approval_id FROM approvals WHERE status = 'PENDING' AND expires_at > ?"
        params: list[object] = [time.time()]
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        query += " ORDER BY created_at"
        with self._connect() as conn:
            identifiers = [row["approval_id"] for row in conn.execute(query, params)]
        return [self.get(identifier) for identifier in identifiers]

    def decide(
        self,
        approval_id: str,
        decision: str,
        actor: str = "local-user",
        child_actions: Optional[list[str]] = None,
    ) -> dict:
        raw_decision = str(decision).strip().casefold()
        outcome = {
            "approve": "APPROVED",
            "approved": "APPROVED",
            "reject": "REJECTED",
            "rejected": "REJECTED",
        }.get(raw_decision, "")
        if outcome not in {"APPROVED", "REJECTED"}:
            raise ValueError("Entscheidung muss approve oder reject sein.")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Freigabe nicht gefunden: {approval_id}")
            if row["status"] != "PENDING":
                raise ValueError("Freigabe wurde bereits entschieden.")
            if float(row["expires_at"]) <= time.time():
                conn.execute(
                    "UPDATE approvals SET status = 'EXPIRED' WHERE approval_id = ?",
                    (approval_id,),
                )
                raise ValueError("Freigabe ist abgelaufen.")
            details = _load(row["details_json"])
            if child_actions:
                details["child_actions"] = sorted(
                    {str(item).strip() for item in child_actions if str(item).strip()}
                )
            conn.execute(
                """
                UPDATE approvals
                SET status = ?, details_json = ?, decided_at = ?, decided_by = ?
                WHERE approval_id = ?
                """,
                (
                    outcome,
                    json.dumps(details, ensure_ascii=False, sort_keys=True),
                    time.time(),
                    str(actor or "local-user"),
                    approval_id,
                ),
            )
        return self.get(approval_id)

    def consume(
        self,
        approval_id: str,
        expected_action: str,
        expected_job_id: str = "",
    ) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
            if row is None:
                raise ValueError("Freigabe nicht gefunden.")
            if row["status"] != "APPROVED":
                raise PermissionError("Aktion wurde nicht freigegeben.")
            if row["used_at"] is not None:
                raise PermissionError("Freigabe wurde bereits verwendet.")
            if float(row["expires_at"]) <= time.time():
                raise PermissionError("Freigabe ist abgelaufen.")
            if row["action_type"] != expected_action:
                raise PermissionError("Freigabe passt nicht zur Aktion.")
            if expected_job_id and row["job_id"] != expected_job_id:
                raise PermissionError("Freigabe passt nicht zum Job.")
            conn.execute(
                "UPDATE approvals SET used_at = ? WHERE approval_id = ?",
                (time.time(), approval_id),
            )
        return self.get(approval_id)

    def _validate_parent(self, parent_id: str, job_id: str, action: str) -> None:
        parent = self.get(parent_id)
        if parent["job_id"] != job_id:
            raise PermissionError("Kind-Freigabe muss zum selben Job gehoeren.")
        if parent["status"] != "APPROVED" or parent["expires_at"] <= time.time():
            raise PermissionError("Eltern-Freigabe ist nicht mehr gueltig.")
        allowed = set(parent["details"].get("child_actions") or [])
        if action not in allowed:
            raise PermissionError("Eltern-Freigabe deckt diese Kind-Aktion nicht ab.")

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    parent_approval_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    decided_at REAL,
                    decided_by TEXT,
                    used_at REAL,
                    token_hash TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_approvals_pending ON approvals(status, expires_at)"
            )

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _load_secret(self) -> bytes:
        try:
            return self.secret_path.read_bytes()
        except OSError:
            secret = secrets.token_bytes(32)
            self.secret_path.write_bytes(secret)
            try:
                self.secret_path.chmod(0o600)
            except OSError:
                pass
            return secret

    def _sign(self, approval_id: str, job_id: str, action: str, expires_at: float) -> str:
        message = f"{approval_id}|{job_id}|{action}|{expires_at:.6f}".encode("utf-8")
        return hmac.new(self._secret, message, hashlib.sha256).hexdigest()


def _load(value: str) -> dict:
    try:
        result = json.loads(value or "{}")
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError:
        return {}
