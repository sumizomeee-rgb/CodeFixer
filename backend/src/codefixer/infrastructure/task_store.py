from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.config_store import canonical_json


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _task_id(provider: str, external_id: str, project_id: str) -> str:
    digest = hashlib.sha256(f'{provider}:{external_id}:{project_id}'.encode()).hexdigest()[:16]
    return f'task-{digest}'


class TaskStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def ingest(self, ticket: IngestedTicket, project_id: str, execution_mode: str) -> dict[str, Any]:
        content_hash = hashlib.sha256(canonical_json(ticket.payload).encode()).hexdigest()
        with self.connection:
            row = self.connection.execute(
                'SELECT id, current_snapshot_id FROM ticket_records WHERE provider_instance_id=? AND external_ticket_id=?',
                (ticket.provider_instance_id, ticket.external_ticket_id),
            ).fetchone()
            if row is None:
                cursor = self.connection.execute(
                    '''INSERT INTO ticket_records(provider_instance_id, external_ticket_id, title, eligible, external_version)
                       VALUES (?, ?, ?, ?, ?)''',
                    (ticket.provider_instance_id, ticket.external_ticket_id, ticket.title, int(ticket.eligible), ticket.external_version),
                )
                if cursor.lastrowid is None:
                    raise RuntimeError('ticket record insert returned no row id')
                record_id = cursor.lastrowid
            else:
                record_id = int(row['id'])
                self.connection.execute(
                    '''UPDATE ticket_records SET title=?, eligible=?, external_version=?, updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                    (ticket.title, int(ticket.eligible), ticket.external_version, record_id),
                )
            snap = self.connection.execute(
                'SELECT id FROM ticket_snapshots WHERE ticket_record_id=? AND content_hash=?',
                (record_id, content_hash),
            ).fetchone()
            if snap is None:
                cursor = self.connection.execute(
                    '''INSERT INTO ticket_snapshots(ticket_record_id, content_hash, title, payload_json, external_version)
                       VALUES (?, ?, ?, ?, ?)''',
                    (record_id, content_hash, ticket.title, canonical_json(ticket.payload), ticket.external_version),
                )
                if cursor.lastrowid is None:
                    raise RuntimeError('ticket snapshot insert returned no row id')
                snapshot_id = cursor.lastrowid
            else:
                snapshot_id = int(snap['id'])
            self.connection.execute('UPDATE ticket_records SET current_snapshot_id=? WHERE id=?', (snapshot_id, record_id))

            task_id = _task_id(ticket.provider_instance_id, ticket.external_ticket_id, project_id)
            task = self.connection.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
            if task is None:
                status = 'queued' if execution_mode == 'automatic' and ticket.eligible else 'awaiting_start'
                if not ticket.eligible:
                    status = 'canceled'
                self.connection.execute(
                    '''INSERT INTO tasks(id, ticket_record_id, project_id, status) VALUES (?, ?, ?, ?)''',
                    (task_id, record_id, project_id, status),
                )
                self._event(task_id, 'ticket_ingested', {'snapshotId': snapshot_id, 'status': status})
                if status == 'queued':
                    self._create_run(task_id, execution_mode)
            else:
                self._event(task_id, 'ticket_updated', {'snapshotId': snapshot_id})
            return self.get_task(task_id)

    def _event(self, task_id: str, event_type: str, payload: dict[str, object]) -> None:
        self.connection.execute(
            'INSERT INTO task_events(event_type, payload_json) VALUES (?, ?)',
            (event_type, canonical_json({'taskId': task_id, **payload})),
        )

    def _create_run(self, task_id: str, execution_mode: str) -> str:
        existing = self.connection.execute(
            "SELECT id FROM task_runs WHERE task_id=? AND status IN ('queued','running')", (task_id,)
        ).fetchone()
        if existing is not None:
            return str(existing['id'])
        run_id = f'run-{uuid.uuid4().hex[:18]}'
        self.connection.execute(
            'INSERT INTO task_runs(id, task_id, status, execution_mode_snapshot) VALUES (?, ?, ?, ?)',
            (run_id, task_id, 'queued', execution_mode),
        )
        self.connection.execute(
            'UPDATE tasks SET current_run_id=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (run_id, 'queued', task_id),
        )
        self._event(task_id, 'run_queued', {'runId': run_id, 'mode': execution_mode})
        return run_id

    def start_task(self, task_id: str, execution_mode: str) -> dict[str, Any]:
        task = self.connection.execute('SELECT status FROM tasks WHERE id=?', (task_id,)).fetchone()
        if task is None:
            raise KeyError(task_id)
        if task['status'] not in {'awaiting_start', 'failed', 'canceled'}:
            raise ValueError(f"task cannot start from {task['status']}")
        with self.connection:
            self._create_run(task_id, execution_mode)
        return self.get_task(task_id)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        row = self.connection.execute('SELECT status,current_run_id FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        with self.connection:
            if row['status'] in {'awaiting_start', 'queued'}:
                self.connection.execute(
                    "UPDATE tasks SET status='canceled',updated_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,)
                )
                if row['current_run_id']:
                    self.connection.execute(
                        "UPDATE task_runs SET status='canceled',finished_at=? WHERE id=?", (_now(), row['current_run_id'])
                    )
                self._event(task_id, 'task_canceled', {})
            elif row['status'] == 'running':
                self.connection.execute(
                    "UPDATE tasks SET status='cancel_requested',updated_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,)
                )
                self._event(task_id, 'cancel_requested', {})
            else:
                raise ValueError(f"task cannot cancel from {row['status']}")
        return self.get_task(task_id)

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        sql = '''SELECT t.*, tr.provider_instance_id, tr.external_ticket_id, tr.title
                 FROM tasks t JOIN ticket_records tr ON tr.id=t.ticket_record_id'''
        params: tuple[object, ...] = ()
        if status:
            sql += ' WHERE t.status=?'
            params = (status,)
        sql += ' ORDER BY t.updated_at DESC, t.created_at DESC'
        return [dict(row) for row in self.connection.execute(sql, params).fetchall()]

    def get_task(self, task_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            '''SELECT t.*, tr.provider_instance_id, tr.external_ticket_id, tr.title, tr.current_snapshot_id
               FROM tasks t JOIN ticket_records tr ON tr.id=t.ticket_record_id WHERE t.id=?''',
            (task_id,),
        ).fetchone()
        if row is None:
            raise KeyError(task_id)
        result = dict(row)
        result['runs'] = [
            dict(item)
            for item in self.connection.execute(
                'SELECT * FROM task_runs WHERE task_id=? ORDER BY created_at DESC', (task_id,)
            ).fetchall()
        ]
        events = self.connection.execute(
            "SELECT id,event_type,payload_json,created_at FROM task_events WHERE json_extract(payload_json,'$.taskId')=? ORDER BY id",
            (task_id,),
        ).fetchall()
        result['events'] = [{**dict(item), 'payload': json.loads(item['payload_json'])} for item in events]
        return result
