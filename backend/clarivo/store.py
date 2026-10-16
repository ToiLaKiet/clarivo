"""Migration-backed, versioned SQLite workspace store."""

import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = PROJECT_ROOT / "database" / "migrations"
DEFAULT_DB = PROJECT_ROOT / "database" / "data" / "clarivo.sqlite3"


class NotFound(Exception):
    pass


class VersionConflict(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def request_hash(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class WorkspaceStore:
    def __init__(self, path=None):
        self.path = Path(path or os.getenv("CLARVIO_DB", DEFAULT_DB))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 5000")
        return db

    def migrate(self):
        with closing(self.connect()) as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
            for path in sorted(MIGRATIONS.glob("*.sql")):
                version = path.stem.split("_", 1)[0]
                db.execute("BEGIN IMMEDIATE")
                try:
                    applied = db.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone()
                    if not applied:
                        statement = ""
                        for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
                            statement += line
                            if sqlite3.complete_statement(statement):
                                db.execute(statement)
                                statement = ""
                        if statement.strip():
                            raise ValueError(f"Incomplete SQL migration: {path.name}")
                        db.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, utc_now()))
                    db.commit()
                except Exception:
                    db.rollback()
                    raise

    def schema_version(self):
        with closing(self.connect()) as db:
            row = db.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1").fetchone()
        return row[0] if row else None

    @staticmethod
    def _response(row, snapshot):
        return {
            "id": row["id"], "name": snapshot["name"], "summary": snapshot["summary"],
            "status": snapshot["status"], "version": row["current_version"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    @staticmethod
    def _replay(db, scope, key, fingerprint):
        row = db.execute(
            "SELECT request_hash, response_json FROM idempotency_keys WHERE scope = ? AND key = ?",
            (scope, key),
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != fingerprint:
            raise IdempotencyConflict("This idempotency key was already used for a different request")
        return json.loads(row["response_json"])

    @staticmethod
    def _record(db, scope, key, fingerprint, response):
        db.execute(
            "INSERT INTO idempotency_keys (scope, key, request_hash, response_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (scope, key, fingerprint, canonical_json(response), utc_now()),
        )

    def create(self, name, key):
        name = name.strip()
        scope = "workspaces:create"
        fingerprint = request_hash({"name": name})
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                replay = self._replay(db, scope, key, fingerprint)
                if replay is not None:
                    db.commit()
                    return replay
                workspace_id = str(uuid.uuid4())
                timestamp = utc_now()
                snapshot = {"name": name, "summary": "", "status": "clarifying"}
                db.execute(
                    "INSERT INTO workspaces (id, name, status, current_version, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                    (workspace_id, name, snapshot["status"], timestamp, timestamp),
                )
                db.execute(
                    "INSERT INTO plan_versions (workspace_id, version, status, snapshot_json, created_at) VALUES (?, 1, ?, ?, ?)",
                    (workspace_id, snapshot["status"], canonical_json(snapshot), timestamp),
                )
                row = db.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
                response = self._response(row, snapshot)
                self._record(db, scope, key, fingerprint, response)
                db.commit()
                return response
            except Exception:
                db.rollback()
                raise

    def list(self):
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT w.*, v.snapshot_json FROM workspaces w JOIN plan_versions v "
                "ON v.workspace_id = w.id AND v.version = w.current_version "
                "ORDER BY w.created_at DESC, w.id DESC"
            ).fetchall()
        return [self._response(row, json.loads(row["snapshot_json"])) for row in rows]

    def get(self, workspace_id):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT w.*, v.snapshot_json FROM workspaces w JOIN plan_versions v "
                "ON v.workspace_id = w.id AND v.version = w.current_version WHERE w.id = ?",
                (workspace_id,),
            ).fetchone()
        if row is None:
            raise NotFound("Workspace not found")
        return self._response(row, json.loads(row["snapshot_json"]))

    def versions(self, workspace_id):
        self.get(workspace_id)
        with closing(self.connect()) as db:
            rows = db.execute(
                "SELECT version, status, snapshot_json, created_at FROM plan_versions "
                "WHERE workspace_id = ? ORDER BY version DESC", (workspace_id,),
            ).fetchall()
        return [{"version": row["version"], "status": row["status"],
                 "name": json.loads(row["snapshot_json"])["name"],
                 "summary": json.loads(row["snapshot_json"])["summary"],
                 "created_at": row["created_at"]} for row in rows]

    def version(self, workspace_id, version):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT version, status, snapshot_json, created_at FROM plan_versions "
                "WHERE workspace_id = ? AND version = ?", (workspace_id, version),
            ).fetchone()
        if row is None:
            raise NotFound("Plan version not found")
        snapshot = json.loads(row["snapshot_json"])
        return {"workspace_id": workspace_id, "version": row["version"],
                "status": row["status"], "name": snapshot["name"],
                "summary": snapshot["summary"], "created_at": row["created_at"]}

    def update(self, workspace_id, expected_version, name, summary, key):
        name = name.strip()
        summary = summary.strip()
        scope = f"workspaces:{workspace_id}:update"
        fingerprint = request_hash({"expected_version": expected_version, "name": name, "summary": summary})
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                replay = self._replay(db, scope, key, fingerprint)
                if replay is not None:
                    db.commit()
                    return replay
                row = db.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
                if row is None:
                    raise NotFound("Workspace not found")
                if row["current_version"] != expected_version:
                    raise VersionConflict(f"Workspace is at version {row['current_version']}; refresh before saving")
                version = expected_version + 1
                timestamp = utc_now()
                snapshot = {"name": name, "summary": summary, "status": row["status"]}
                db.execute(
                    "INSERT INTO plan_versions (workspace_id, version, status, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?)",
                    (workspace_id, version, row["status"], canonical_json(snapshot), timestamp),
                )
                db.execute(
                    "UPDATE workspaces SET name = ?, current_version = ?, updated_at = ? WHERE id = ?",
                    (name, version, timestamp, workspace_id),
                )
                updated = db.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
                response = self._response(updated, snapshot)
                self._record(db, scope, key, fingerprint, response)
                db.commit()
                return response
            except Exception:
                db.rollback()
                raise
