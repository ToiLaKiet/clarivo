# CLARVIO

CLARVIO is a customer request and delivery planning workspace. The current implementation is the database foundation from [ticket #13](https://github.com/ToiLaKiet/clarivo/issues/13): create a workspace, save a request summary as a new plan version, reopen it after a restart, and inspect its version history. Document intake and the later planning workflow follow in separate tickets.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

Open <http://127.0.0.1:8000>. The API contract is at <http://127.0.0.1:8000/docs>. The SQLite database defaults to `database/data/clarivo.sqlite3`; set `CLARVIO_DB` to choose another path. Migrations in `database/migrations/` apply automatically at startup.

The API and persistence code are in `backend/`; the browser UI is in `frontend/`; SQL migrations and local database data are in `database/`. Run commands from the repository root.

## Database contract

The first migration creates workspaces, immutable plan-version snapshots, and idempotency records. A workspace update inserts the next snapshot and advances the current-version pointer in one transaction. Writes require an `Idempotency-Key` header; updates also require `expected_version`. A stale version or a key reused with different input returns HTTP 409.

The [database decision and logical model](docs/adr/0001-versioned-workspace-store.md) cover later sources, messages, requirements, assumptions, tasks, assignments, and approval. New physical tables should be added in new numbered migrations as those features are built.

The current screen has no customer or manager authentication. Ticket #1 adds workspace access control before shared customer use.

## Tests

```bash
pip install -r requirements-dev.txt
python3 -m pytest -q
```
