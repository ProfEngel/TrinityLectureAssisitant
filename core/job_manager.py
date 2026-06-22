"""Persistent job records and quality-gated execution steps."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Iterable, Optional


JOB_STATUSES = {
    "PENDING",
    "RUNNING",
    "WAITING_FOR_INPUT",
    "WAITING_FOR_APPROVAL",
    "QUEUED",
    "SUCCEEDED",
    "FAILED",
    "NEEDS_ESCALATION",
    "CANCELLED",
}
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "NEEDS_ESCALATION", "CANCELLED"}


class JobManager:
    """Store non-trivial work as recoverable local jobs."""

    def __init__(self, home: Optional[str | Path] = None):
        root = Path(home or Path(__file__).resolve().parents[1]).resolve()
        self.db_path = root / "memory" / "jobs.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def create_job(
        self,
        title: str,
        source: str = "desktop",
        route: str = "local",
        risk_level: str = "low",
        plan: Optional[Iterable[dict]] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        job_id = f"job_{uuid.uuid4().hex}"
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, title, status, source, route, risk_level,
                    created_at, updated_at, metadata_json
                ) VALUES (?, ?, 'PENDING', ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    str(title).strip() or "Trinity-Auftrag",
                    str(source),
                    str(route),
                    str(risk_level),
                    now,
                    now,
                    _dump(metadata or {}),
                ),
            )
            for position, step in enumerate(plan or [], start=1):
                self._insert_step(conn, job_id, position, step)
        return self.get(job_id)

    def get(self, job_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Job nicht gefunden: {job_id}")
            steps = conn.execute(
                "SELECT * FROM job_steps WHERE job_id = ? ORDER BY position",
                (job_id,),
            ).fetchall()
            events = conn.execute(
                """
                SELECT timestamp, event_type, message, details_json
                FROM job_events WHERE job_id = ? ORDER BY id
                """,
                (job_id,),
            ).fetchall()
        return {
            "job_id": row["job_id"],
            "title": row["title"],
            "status": row["status"],
            "source": row["source"],
            "route": row["route"],
            "risk_level": row["risk_level"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "metadata": _load(row["metadata_json"]),
            "steps": [
                {
                    "step_id": step["step_id"],
                    "position": step["position"],
                    "title": step["title"],
                    "quality_gate": bool(step["quality_gate"]),
                    "status": step["status"],
                    "details": _load(step["details_json"]),
                }
                for step in steps
            ],
            "events": [
                {
                    "timestamp": event["timestamp"],
                    "type": event["event_type"],
                    "message": event["message"],
                    "details": _load(event["details_json"]),
                }
                for event in events
            ],
        }

    def list(self, limit: int = 50, status: str = "") -> list[dict]:
        query = "SELECT job_id FROM jobs"
        params: list[object] = []
        if status:
            query += " WHERE status = ?"
            params.append(_status(status))
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        with self._connect() as conn:
            identifiers = [row["job_id"] for row in conn.execute(query, params)]
        return [self.get(job_id) for job_id in identifiers]

    def set_status(
        self,
        job_id: str,
        status: str,
        message: str = "",
        details: Optional[dict] = None,
    ) -> dict:
        clean_status = _status(status)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Job nicht gefunden: {job_id}")
            if row["status"] in TERMINAL_STATUSES and clean_status != row["status"]:
                raise ValueError("Abgeschlossene Jobs koennen nicht umgestellt werden.")
            now = time.time()
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (clean_status, now, job_id),
            )
            self._event(conn, job_id, f"STATUS_{clean_status}", message, details)
        return self.get(job_id)

    def start(self, job_id: str, message: str = "Ausfuehrung gestartet.") -> dict:
        return self.set_status(job_id, "RUNNING", message)

    def complete(
        self,
        job_id: str,
        message: str = "Auftrag abgeschlossen.",
        details: Optional[dict] = None,
    ) -> dict:
        return self.set_status(job_id, "SUCCEEDED", message, details)

    def fail(
        self,
        job_id: str,
        message: str,
        details: Optional[dict] = None,
        escalation: bool = False,
    ) -> dict:
        return self.set_status(
            job_id,
            "NEEDS_ESCALATION" if escalation else "FAILED",
            message,
            details,
        )

    def add_step(
        self,
        job_id: str,
        title: str,
        quality_gate: bool = False,
        details: Optional[dict] = None,
    ) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(position), 0) AS position FROM job_steps WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            self._insert_step(
                conn,
                job_id,
                int(row["position"]) + 1,
                {
                    "title": title,
                    "quality_gate": quality_gate,
                    "details": details or {},
                },
            )
        return self.get(job_id)

    def update_step(
        self,
        job_id: str,
        step_id: str,
        status: str,
        details: Optional[dict] = None,
    ) -> dict:
        clean_status = _step_status(status)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT step_id FROM job_steps WHERE job_id = ? AND step_id = ?",
                (job_id, step_id),
            ).fetchone()
            if row is None:
                raise ValueError(f"Schritt nicht gefunden: {step_id}")
            conn.execute(
                """
                UPDATE job_steps SET status = ?, details_json = ?
                WHERE job_id = ? AND step_id = ?
                """,
                (clean_status, _dump(details or {}), job_id, step_id),
            )
            conn.execute(
                "UPDATE jobs SET updated_at = ? WHERE job_id = ?",
                (time.time(), job_id),
            )
            self._event(
                conn,
                job_id,
                f"STEP_{clean_status}",
                f"Schritt {step_id}: {clean_status}",
                details,
            )
        return self.get(job_id)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    route TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS job_steps (
                    step_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    quality_gate INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                );
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
                );
                CREATE INDEX IF NOT EXISTS idx_jobs_updated ON jobs(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_job_steps_job ON job_steps(job_id, position);
                CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id, id);
                """
            )

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _insert_step(self, conn, job_id: str, position: int, step: dict) -> None:
        title = str(step.get("title", "")).strip()
        if not title:
            raise ValueError("Ein Job-Schritt braucht einen Titel.")
        conn.execute(
            """
            INSERT INTO job_steps (
                step_id, job_id, position, title, quality_gate, status, details_json
            ) VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            (
                f"step_{uuid.uuid4().hex}",
                job_id,
                position,
                title,
                int(bool(step.get("quality_gate", False))),
                _dump(step.get("details") or {}),
            ),
        )

    @staticmethod
    def _event(conn, job_id: str, event_type: str, message: str, details: Optional[dict]):
        conn.execute(
            """
            INSERT INTO job_events (job_id, timestamp, event_type, message, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                job_id,
                time.time(),
                event_type,
                str(message or ""),
                _dump(details or {}),
            ),
        )


def _status(value: str) -> str:
    normalized = str(value).strip().upper()
    if normalized not in JOB_STATUSES:
        raise ValueError(f"Ungueltiger Job-Status: {value}")
    return normalized


def _step_status(value: str) -> str:
    normalized = str(value).strip().upper()
    if normalized not in {"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "SKIPPED"}:
        raise ValueError(f"Ungueltiger Schritt-Status: {value}")
    return normalized


def _dump(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(value: str) -> dict:
    try:
        data = json.loads(value or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
