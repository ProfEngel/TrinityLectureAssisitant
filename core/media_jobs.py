"""Idempotent background media jobs shared by voice and chat clients."""
import contextvars
import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from chat_protocol import append_chat_event
from tenant_context import tenant_history_path
from unified_session import UnifiedSessionStore
from voice.diagnostics import diagnostic


# Keep one model slot available for conversation even if several media briefs
# arrive together. No resubmission/retry of paid provider jobs is introduced.
_MEDIA_WORKER = threading.BoundedSemaphore(1)


def _db(home):
    path = Path(home) / 'memory/media_jobs.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.execute('CREATE TABLE IF NOT EXISTS jobs (fingerprint TEXT PRIMARY KEY, id TEXT, status TEXT, created REAL)')
    db.commit()
    path.chmod(0o600)
    return db


def start_media_job(home, query, execute, context):
    history = tenant_history_path(home)
    session = UnifiedSessionStore(home).current()
    normalized = re.sub(r'\W+', ' ', query.lower()).strip()
    fingerprint = hashlib.sha256((str(history) + '\n' + execute.__module__ + '\n' + normalized).encode()).hexdigest()
    job_id = uuid.uuid4().hex
    with _db(home) as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT status,created FROM jobs WHERE fingerprint=?', (fingerprint,)).fetchone()
        if existing and time.time() - existing[1] < 3600:
            done = existing[0] == 'complete'
            return {'has_payload': False, 'search_context': '', 'direct_answer':
                'Das Medium wurde bereits erstellt; öffne den Medien-Player.' if done else
                'Dieser Medienauftrag wurde bereits gestartet. Ich erstelle ihn nicht erneut.'}
        db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?,?)', (fingerprint, job_id, 'running', time.time()))
    brain = context['brain']
    snapshot = contextvars.copy_context()

    def run():
        result = {}
        try:
            with _MEDIA_WORKER:
                result = brain._run_media_skill(execute, query, context)
            text = result.get('direct_answer') or result.get('search_context') or (
                'Das Medium ist fertig und im Medien-Player verfügbar.' if result.get('has_payload') else 'Das Medium konnte nicht erstellt werden.')
            append_chat_event(history, {'request_id': job_id, 'source': 'media-job',
                'session_id': session.id, 'session_name': session.title,
                'role': 'assistant', 'text': text,
                'payload_html': result.get('html_payload', '') if result.get('has_payload') else ''})
        except Exception:
            diagnostic(home, 'Media', 'finished')
            append_chat_event(history, {'request_id': job_id, 'source': 'media-job',
                'session_id': session.id, 'session_name': session.title,
                'role': 'assistant', 'text': 'Der Medienauftrag ist fehlgeschlagen; kein weiterer Auftrag wurde gestartet.', 'payload_html': ''})
        finally:
            with _db(home) as db:
                db.execute('UPDATE jobs SET status=? WHERE fingerprint=?', ('complete' if result.get('has_payload') else 'failed', fingerprint))

    threading.Thread(target=lambda: snapshot.run(run), name='trinity-media-' + job_id[:8], daemon=True).start()
    return {'has_payload': False, 'search_context': '', 'direct_answer': 'Ich erstelle das Medium. Du findest es anschließend im Medien-Player.'}
