"""Local SQLite memory and session store for Trinity."""

from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "memory" / "trinity_memory.sqlite3"
DEFAULT_CHAT_HISTORY = ROOT_DIR / "memory" / "classic_chat_history.jsonl"


def _now() -> float:
    return time.time()


def _json(data) -> str:
    return json.dumps(data or {}, ensure_ascii=False, sort_keys=True)


def _snippet(text: str, limit: int = 140) -> str:
    cleaned = " ".join(str(text or "").split())
    return cleaned[: limit - 1] + "…" if len(cleaned) > limit else cleaned


def extract_tags(text: str, explicit_tags=None, limit: int = 8):
    """Extract stable, lightweight tags without adding another dependency."""
    tags = []
    for tag in explicit_tags or []:
        normalized = str(tag).strip().strip("#").casefold()
        if normalized and normalized not in tags:
            tags.append(normalized)

    raw_text = str(text or "")
    for match in re.findall(r"#([\wäöüÄÖÜß-]{2,40})", raw_text):
        normalized = match.casefold()
        if normalized not in tags:
            tags.append(normalized)

    stopwords = {
        "aber",
        "auch",
        "bitte",
        "dann",
        "dass",
        "dies",
        "eine",
        "einer",
        "eines",
        "haben",
        "kann",
        "nicht",
        "oder",
        "sich",
        "sind",
        "trinity",
        "über",
        "wenn",
        "werden",
        "wird",
    }
    for word in re.findall(r"[A-Za-zÄÖÜäöüß][\wÄÖÜäöüß-]{4,}", raw_text):
        normalized = word.casefold()
        if normalized in stopwords or normalized in tags:
            continue
        tags.append(normalized)
        if len(tags) >= limit:
            break
    return tags[:limit]


class MemoryStore:
    """Small local store for sessions, memories, tags and graph links."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _ensure_schema(self):
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    summary TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id, created_at);

                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'manual',
                    session_id TEXT,
                    weight REAL NOT NULL DEFAULT 0.5,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    baked_at REAL,
                    superseded_by TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_memories_created
                    ON memories(created_at);
                CREATE INDEX IF NOT EXISTS idx_memories_weight
                    ON memories(weight);

                CREATE TABLE IF NOT EXISTS memory_tags (
                    memory_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY(memory_id, tag),
                    FOREIGN KEY(memory_id) REFERENCES memories(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_memory_tags_tag ON memory_tags(tag);

                CREATE TABLE IF NOT EXISTS memory_edges (
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 0.3,
                    created_at REAL NOT NULL,
                    PRIMARY KEY(source_id, target_id, relation),
                    FOREIGN KEY(source_id) REFERENCES memories(id) ON DELETE CASCADE,
                    FOREIGN KEY(target_id) REFERENCES memories(id) ON DELETE CASCADE
                );
                """
            )

    def ensure_session(self, session_id=None, title="Trinity Session"):
        now = _now()
        session_id = session_id or uuid.uuid4().hex[:12]
        with self.connect() as db:
            existing = db.execute(
                "SELECT id FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if not existing:
                db.execute(
                    """
                    INSERT INTO sessions(id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (session_id, title, now, now),
                )
        return session_id

    def create_session(self, title="Trinity Session"):
        return self.ensure_session(uuid.uuid4().hex[:12], title)

    def list_sessions(self, limit=20):
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    """
                    SELECT id, title, created_at, updated_at, status, summary
                    FROM sessions
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                )
            ]

    def add_message(self, session_id, role, content, metadata=None):
        session_id = self.ensure_session(session_id)
        now = _now()
        message_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO messages(id, session_id, role, content, created_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (message_id, session_id, role, str(content or ""), now, _json(metadata)),
            )
            db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
        return message_id

    def remember(
        self,
        text,
        tags=None,
        *,
        kind="episodic",
        source="manual",
        session_id=None,
        weight=0.55,
        baked=False,
        metadata=None,
    ):
        cleaned = str(text or "").strip()
        if not cleaned:
            raise ValueError("Memory text must not be empty.")
        if session_id:
            self.ensure_session(session_id)
        memory_id = uuid.uuid4().hex
        now = _now()
        memory_tags = extract_tags(cleaned, tags)
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO memories(
                    id, kind, text, summary, source, session_id, weight,
                    created_at, updated_at, baked_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    kind,
                    cleaned,
                    _snippet(cleaned, 220),
                    source,
                    session_id,
                    max(0.0, min(1.0, float(weight))),
                    now,
                    now,
                    now if baked else None,
                    _json(metadata),
                ),
            )
            db.executemany(
                "INSERT OR IGNORE INTO memory_tags(memory_id, tag) VALUES (?, ?)",
                [(memory_id, tag) for tag in memory_tags],
            )
        return memory_id

    def search(self, query="", *, tags=None, limit=8):
        terms = [term.casefold() for term in str(query or "").split() if term]
        tags = [str(tag).strip().strip("#").casefold() for tag in tags or [] if tag]
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT m.*
                FROM memories m
                ORDER BY m.weight DESC, m.updated_at DESC
                LIMIT 200
                """
            ).fetchall()
            results = []
            for row in rows:
                tag_rows = db.execute(
                    "SELECT tag FROM memory_tags WHERE memory_id = ?",
                    (row["id"],),
                ).fetchall()
                row_tags = [item["tag"] for item in tag_rows]
                haystack = f"{row['text']} {' '.join(row_tags)}".casefold()
                if terms and not all(term in haystack for term in terms):
                    continue
                if tags and not all(tag in row_tags for tag in tags):
                    continue
                item = dict(row)
                item["tags"] = row_tags
                results.append(item)
                if len(results) >= limit:
                    break
            if results:
                now = _now()
                db.executemany(
                    """
                    UPDATE memories
                    SET weight = MIN(1.0, weight + 0.015), updated_at = ?
                    WHERE id = ?
                    """,
                    [(now, item["id"]) for item in results],
                )
            return results

    def context_for_prompt(self, query, limit=5):
        matches = self.search(query, limit=limit)
        if not matches:
            return ""
        lines = ["--- TRINITY MEMORY ---"]
        for item in matches:
            tags = ", ".join(item.get("tags") or [])
            suffix = f" [{tags}]" if tags else ""
            lines.append(f"- {item['summary'] or _snippet(item['text'])}{suffix}")
        return "\n".join(lines)

    def bake_unbaked(self, batch_size=24):
        now = _now()
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT *
                FROM memories
                WHERE baked_at IS NULL AND superseded_by IS NULL
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (int(batch_size),),
            ).fetchall()
            if not rows:
                return {"baked": 0, "summaries": 0}

            tag_rows = db.execute(
                """
                SELECT memory_id, tag
                FROM memory_tags
                WHERE memory_id IN ({})
                """.format(",".join("?" for _ in rows)),
                [row["id"] for row in rows],
            ).fetchall()
            by_memory = {}
            for tag_row in tag_rows:
                by_memory.setdefault(tag_row["memory_id"], []).append(tag_row["tag"])

            summary_tags = sorted(
                {tag for tags in by_memory.values() for tag in tags}
            )[:10]
            summary_text = "Self-Bake: " + " | ".join(
                _snippet(row["text"], 120) for row in rows
            )
            summary_id = uuid.uuid4().hex
            db.execute(
                """
                INSERT INTO memories(
                    id, kind, text, summary, source, session_id, weight,
                    created_at, updated_at, baked_at, metadata_json
                )
                VALUES (?, 'summary', ?, ?, 'self-bake', ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary_id,
                    summary_text,
                    _snippet(summary_text, 220),
                    rows[-1]["session_id"],
                    min(1.0, max(float(row["weight"]) for row in rows) + 0.08),
                    now,
                    now,
                    now,
                    _json({"source_memory_ids": [row["id"] for row in rows]}),
                ),
            )
            db.executemany(
                "INSERT OR IGNORE INTO memory_tags(memory_id, tag) VALUES (?, ?)",
                [(summary_id, tag) for tag in summary_tags],
            )
            db.execute(
                """
                UPDATE memories
                SET baked_at = ?, updated_at = ?, superseded_by = COALESCE(superseded_by, ?)
                WHERE id IN ({})
                """.format(",".join("?" for _ in rows)),
                [now, now, summary_id, *[row["id"] for row in rows]],
            )
            db.executemany(
                """
                INSERT OR REPLACE INTO memory_edges(
                    source_id, target_id, relation, weight, created_at
                )
                VALUES (?, ?, 'summarizes', 0.75, ?)
                """,
                [(summary_id, row["id"], now) for row in rows],
            )
        self.dream_tick()
        return {"baked": len(rows), "summaries": 1}

    def bake_chat_history(self, history_path=None):
        path = Path(history_path or DEFAULT_CHAT_HISTORY)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {"imported": 0, "baked": 0, "summaries": 0}

        session_id = self.ensure_session("classic", "Classic UI")
        imported = 0
        with self.connect() as db:
            for line in lines:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_id = event.get("event_id") or event.get("request_id")
                text = str(event.get("text") or "").strip()
                role = str(event.get("role") or "unknown")
                if not text or not event_id:
                    continue
                duplicate = db.execute(
                    """
                    SELECT id FROM memories
                    WHERE metadata_json LIKE ?
                    """,
                    (f'%"{event_id}"%',),
                ).fetchone()
                if duplicate:
                    continue
                self.add_message(
                    session_id,
                    role,
                    text,
                    {"source": "classic-history", "event_id": event_id},
                )
                self.remember(
                    f"{role}: {text}",
                    source="classic-history",
                    session_id=session_id,
                    weight=0.5 if role == "user" else 0.58,
                    metadata={"event_id": event_id, "request_id": event.get("request_id")},
                )
                imported += 1
        baked = self.bake_unbaked()
        return {"imported": imported, **baked}

    def compress_context(self, session_id):
        self.ensure_session(session_id)
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,),
            ).fetchall()
        if len(rows) <= 24:
            return {"compressed": 0, "summary": ""}

        middle = rows[3:-20]
        summary = "Kontextkompression: " + " | ".join(
            f"{row['role']}: {_snippet(row['content'], 90)}" for row in middle
        )
        memory_id = self.remember(
            summary,
            tags=["context", "session"],
            kind="context-summary",
            source="context-compression",
            session_id=session_id,
            weight=0.72,
            baked=True,
        )
        with self.connect() as db:
            db.execute(
                "UPDATE sessions SET summary = ?, updated_at = ? WHERE id = ?",
                (_snippet(summary, 900), _now(), session_id),
            )
        return {"compressed": len(middle), "summary": summary, "memory_id": memory_id}

    def dream_tick(self):
        now = _now()
        created = 0
        with self.connect() as db:
            memories = db.execute(
                "SELECT id, weight, created_at FROM memories WHERE superseded_by IS NULL"
            ).fetchall()
            for row in memories:
                age_days = max(0.0, (now - float(row["created_at"])) / 86400)
                if age_days < 2:
                    factor = 0.998
                    bonus = 0.018
                elif age_days < 14:
                    factor = 0.99
                    bonus = 0.0
                elif age_days < 60:
                    factor = 0.975
                    bonus = 0.0
                else:
                    factor = 0.95
                    bonus = 0.0
                next_weight = max(
                    0.08,
                    min(1.0, float(row["weight"]) * factor + bonus),
                )
                db.execute(
                    "UPDATE memories SET weight = ?, updated_at = ? WHERE id = ?",
                    (next_weight, now, row["id"]),
                )

            tag_rows = db.execute(
                """
                SELECT tag, GROUP_CONCAT(memory_id) AS ids
                FROM memory_tags
                GROUP BY tag
                HAVING COUNT(*) > 1
                """
            ).fetchall()
            for row in tag_rows:
                ids = str(row["ids"]).split(",")[:12]
                for index, source_id in enumerate(ids):
                    for target_id in ids[index + 1 :]:
                        db.execute(
                            """
                            INSERT OR IGNORE INTO memory_edges(
                                source_id, target_id, relation, weight, created_at
                            )
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (source_id, target_id, f"tag:{row['tag']}", 0.35, now),
                        )
                        if db.execute("SELECT changes() AS count").fetchone()["count"]:
                            created += 1
            db.execute(
                """
                UPDATE memories
                SET weight = MIN(1.0, weight + 0.02), updated_at = ?
                WHERE id IN (
                    SELECT source_id FROM memory_edges GROUP BY source_id HAVING COUNT(*) >= 2
                )
                """,
                (now,),
            )
        return {"links_created": created}

    def status(self):
        with self.connect() as db:
            memories = db.execute("SELECT COUNT(*) AS count FROM memories").fetchone()
            unbaked = db.execute(
                "SELECT COUNT(*) AS count FROM memories WHERE baked_at IS NULL"
            ).fetchone()
            links = db.execute("SELECT COUNT(*) AS count FROM memory_edges").fetchone()
            bakes = db.execute(
                "SELECT COUNT(*) AS count FROM memories WHERE source = 'self-bake'"
            ).fetchone()
            superseded = db.execute(
                "SELECT COUNT(*) AS count FROM memories WHERE superseded_by IS NOT NULL"
            ).fetchone()
            tag_rows = db.execute(
                """
                SELECT tag, COUNT(*) AS count
                FROM memory_tags
                GROUP BY tag
                ORDER BY count DESC, tag ASC
                LIMIT 8
                """
            ).fetchall()
        return {
            "engine": "sqlite",
            "path": str(self.db_path),
            "memories": int(memories["count"]),
            "unbaked": int(unbaked["count"]),
            "links": int(links["count"]),
            "bakes": int(bakes["count"]),
            "superseded": int(superseded["count"]),
            "rooms": [{"room": row["tag"], "count": row["count"]} for row in tag_rows],
        }

    def graph_data(self, limit=90):
        with self.connect() as db:
            memories = db.execute(
                """
                SELECT id, kind, summary, text, weight
                FROM memories
                WHERE superseded_by IS NULL OR kind = 'summary'
                ORDER BY weight DESC, updated_at DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()
            memory_ids = [row["id"] for row in memories]
            if not memory_ids:
                return {"nodes": [], "links": []}

            placeholders = ",".join("?" for _ in memory_ids)
            tags = db.execute(
                f"""
                SELECT memory_id, tag
                FROM memory_tags
                WHERE memory_id IN ({placeholders})
                """,
                memory_ids,
            ).fetchall()
            edges = db.execute(
                f"""
                SELECT source_id, target_id, relation, weight
                FROM memory_edges
                WHERE source_id IN ({placeholders}) AND target_id IN ({placeholders})
                ORDER BY weight DESC
                LIMIT 180
                """,
                memory_ids * 2,
            ).fetchall()

        nodes = []
        for row in memories:
            nodes.append(
                {
                    "id": f"memory:{row['id']}",
                    "type": "memory",
                    "label": _snippet(row["summary"] or row["text"], 34),
                    "weight": row["weight"],
                }
            )

        tag_counts = {}
        for row in tags:
            tag_counts[row["tag"]] = tag_counts.get(row["tag"], 0) + 1
        top_tags = {tag for tag, _count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:24]}
        for tag in sorted(top_tags):
            nodes.append({"id": f"tag:{tag}", "type": "entity", "label": tag, "weight": tag_counts[tag] / 10})

        links = []
        for row in tags:
            if row["tag"] in top_tags:
                links.append(
                    {
                        "source": f"memory:{row['memory_id']}",
                        "target": f"tag:{row['tag']}",
                        "relation": "tag",
                        "weight": min(0.8, 0.25 + tag_counts[row["tag"]] / 20),
                    }
                )
        for row in edges:
            links.append(
                {
                    "source": f"memory:{row['source_id']}",
                    "target": f"memory:{row['target_id']}",
                    "relation": row["relation"],
                    "weight": row["weight"],
                }
            )
        return {"nodes": nodes, "links": links[:220]}


def render_graph_html(graph):
    """Render a small dependency-free graph view for ClassicUI and CLI export."""
    nodes = graph.get("nodes") or []
    links = graph.get("links") or []
    payload = json.dumps({"nodes": nodes, "links": links}, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
html, body {{ margin:0; background:#09090b; color:#f4f4f5; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
body {{ padding:18px; }}
.empty {{ color:#71717a; text-align:center; padding:80px 20px; }}
svg {{ width:100%; height:520px; border:1px solid #27272a; border-radius:16px; background:radial-gradient(circle at 50% 40%, #18181b, #09090b 70%); }}
line {{ stroke:#a1a1aa; }}
circle {{ fill:#38bdf8; stroke:#e4e4e7; stroke-width:1.2; }}
.node-memory circle {{ fill:#a78bfa; }}
.node-entity circle {{ fill:#22c55e; }}
text {{ fill:#d4d4d8; font-size:11px; paint-order:stroke; stroke:#09090b; stroke-width:3px; }}
.meta {{ display:flex; gap:10px; margin-bottom:12px; color:#a1a1aa; font-size:12px; }}
.pill {{ border:1px solid #27272a; border-radius:999px; padding:6px 10px; background:#121214; }}
</style>
</head>
<body>
<div class="meta"><span class="pill">Memory-Knoten: {len(nodes)}</span><span class="pill">Links: {len(links)}</span></div>
<div id="graph"></div>
<script>
const data = {payload};
const root = document.querySelector("#graph");
if (!data.nodes.length) {{
  root.innerHTML = '<div class="empty"><h2>Noch keine Memory-Knoten</h2><p>Nutze /remember, /memory bake oder den Chat, damit Trinity ihr Memory aufbaut.</p></div>';
}} else {{
  const width = 920, height = 520, cx = width / 2, cy = height / 2;
  const nodes = data.nodes.slice(0, 100);
  const ids = new Set(nodes.map((node) => node.id));
  const positions = new Map();
  nodes.forEach((node, index) => {{
    const angle = (index / Math.max(1, nodes.length)) * Math.PI * 2;
    const base = node.type === "entity" ? 170 : 120 + (index % 5) * 28;
    positions.set(node.id, {{x: cx + Math.cos(angle) * base, y: cy + Math.sin(angle) * base}});
  }});
  const lines = data.links.filter((link) => ids.has(link.source) && ids.has(link.target)).slice(0, 220).map((link) => {{
    const a = positions.get(link.source), b = positions.get(link.target);
    const opacity = Math.max(0.12, Math.min(0.75, Number(link.weight || 0.2)));
    return `<line x1="${{a.x.toFixed(1)}}" y1="${{a.y.toFixed(1)}}" x2="${{b.x.toFixed(1)}}" y2="${{b.y.toFixed(1)}}" stroke-opacity="${{opacity}}" stroke-width="${{1 + opacity * 2}}" />`;
  }}).join("");
  const circles = nodes.map((node) => {{
    const p = positions.get(node.id);
    const r = node.type === "entity" ? 8 : 5 + Math.min(5, Number(node.weight || 0) * 5);
    const label = String(node.label || node.id).slice(0, 32).replace(/[&<>"]/g, (c) => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
    return `<g class="node-${{node.type || "unknown"}}"><circle cx="${{p.x.toFixed(1)}}" cy="${{p.y.toFixed(1)}}" r="${{r.toFixed(1)}}" /><text x="${{(p.x + r + 5).toFixed(1)}}" y="${{(p.y + 4).toFixed(1)}}">${{label}}</text></g>`;
  }}).join("");
  root.innerHTML = `<svg viewBox="0 0 ${{width}} ${{height}}" role="img" aria-label="Trinity Memory Graph"><g>${{lines}}</g><g>${{circles}}</g></svg>`;
}}
</script>
</body>
</html>"""
