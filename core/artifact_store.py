"""Artifact index for Trinity jobs and agent results."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactRecord:
    artifact_id: str
    job_id: str
    kind: str
    title: str
    source_path: str = ""
    url: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "job_id": self.job_id,
            "kind": self.kind,
            "title": self.title,
            "source_path": self.source_path,
            "url": self.url,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class ArtifactStore:
    """Append-only artifact registry.

    Runtime-owned indexes stay local. BrainVault should not receive legacy
    TrinityVault result folders during app updates.
    """

    def __init__(self, root: str | Path, subdir: str = "03_results"):
        self.root = Path(root).expanduser().resolve()
        self.results_root = self.root / subdir if subdir else self.root
        self.index_path = self.results_root / "artifact_index.jsonl"

    def ensure(self) -> Path:
        self.results_root.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.index_path.write_text("", encoding="utf-8")
        return self.index_path

    def register(
        self,
        job_id: str,
        kind: str,
        title: str,
        source_path: str = "",
        url: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactRecord:
        record = ArtifactRecord(
            artifact_id=f"artifact_{uuid.uuid4().hex}",
            job_id=str(job_id),
            kind=str(kind or "file"),
            title=str(title or "Artefakt"),
            source_path=str(source_path or ""),
            url=str(url or ""),
            metadata=metadata or {},
        )
        self.ensure()
        with self.index_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")
        return record

    def list(self, limit: int = 50, job_id: str = "") -> list[dict[str, Any]]:
        self.ensure()
        records = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if job_id and record.get("job_id") != job_id:
                continue
            records.append(record)
        return list(reversed(records))[: max(1, min(int(limit), 500))]
