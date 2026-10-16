import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.clarivo.store import WorkspaceStore


def test_workspace_survives_restart_with_immutable_versions(tmp_path):
    database = tmp_path / "clarivo.sqlite3"
    with TestClient(create_app(database)) as client:
        created = client.post(
            "/api/workspaces", json={"name": "Booking request"},
            headers={"Idempotency-Key": "create-booking"},
        )
        assert created.status_code == 201
        workspace = created.json()
        assert workspace["version"] == 1
        assert workspace["status"] == "clarifying"
        changed = client.put(
            f"/api/workspaces/{workspace['id']}",
            json={"expected_version": 1, "name": "Booking request", "summary": "Customers book appointments."},
            headers={"Idempotency-Key": "summary-v2"},
        )
        assert changed.status_code == 200
        assert changed.json()["version"] == 2

    with TestClient(create_app(database)) as restarted:
        assert restarted.get("/api/health").json()["schema_version"] == "0001"
        reopened = restarted.get(f"/api/workspaces/{workspace['id']}")
        assert reopened.status_code == 200
        assert reopened.json()["summary"] == "Customers book appointments."
        assert reopened.json()["version"] == 2
        assert len(restarted.get("/api/workspaces").json()) == 1
        history = restarted.get(f"/api/workspaces/{workspace['id']}/versions").json()
        assert [version["version"] for version in history] == [2, 1]
        assert restarted.get(f"/api/workspaces/{workspace['id']}/versions/1").json()["summary"] == ""
        assert restarted.get("/").status_code == 200
        assert "Create workspace" in restarted.get("/static/app.js").text

    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM plan_versions").fetchone()[0] == 2


def test_idempotency_stale_writes_and_key_reuse(tmp_path):
    with TestClient(create_app(tmp_path / "clarivo.sqlite3")) as client:
        create_headers = {"Idempotency-Key": "same-create"}
        first = client.post("/api/workspaces", json={"name": "First"}, headers=create_headers).json()
        repeated = client.post("/api/workspaces", json={"name": "First"}, headers=create_headers).json()
        assert repeated == first
        assert client.post("/api/workspaces", json={"name": "Different"}, headers=create_headers).status_code == 409
        assert len(client.get("/api/workspaces").json()) == 1

        path = f"/api/workspaces/{first['id']}"
        body = {"expected_version": 1, "name": "First", "summary": "Initial summary"}
        saved = client.put(path, json=body, headers={"Idempotency-Key": "update-one"}).json()
        assert saved["version"] == 2
        assert client.put(path, json=body, headers={"Idempotency-Key": "update-one"}).json() == saved
        assert client.put(path, json={**body, "summary": "Changed"}, headers={"Idempotency-Key": "update-one"}).status_code == 409
        assert client.put(path, json=body, headers={"Idempotency-Key": "stale-write"}).status_code == 409
        assert [item["version"] for item in client.get(f"{path}/versions").json()] == [2, 1]


def test_failed_write_rolls_back_snapshot_and_pointer(tmp_path):
    store = WorkspaceStore(tmp_path / "clarivo.sqlite3")
    created = store.create("Valid", "create-valid")
    with pytest.raises(sqlite3.IntegrityError):
        store.update(created["id"], 1, " ", "Should not persist", "bad-update")
    assert store.get(created["id"])["version"] == 1
    assert [item["version"] for item in store.versions(created["id"])] == [1]


def test_blank_names_and_missing_workspaces(tmp_path):
    with TestClient(create_app(tmp_path / "clarivo.sqlite3")) as client:
        assert client.post("/api/workspaces", json={"name": "   "}, headers={"Idempotency-Key":"blank"}).status_code == 422
        assert client.get("/api/workspaces/missing").status_code == 404
        assert client.get("/api/workspaces/missing/versions").status_code == 404
