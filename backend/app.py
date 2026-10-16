"""CLARVIO workspace API and first persistent workspace screen."""

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.clarivo.store import IdempotencyConflict, NotFound, VersionConflict, WorkspaceStore


WEB = Path(__file__).resolve().parent.parent / "frontend"


class NewWorkspace(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class UpdateWorkspace(BaseModel):
    expected_version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(max_length=5000)


def _valid_name(name):
    if not name.strip():
        raise HTTPException(422, "Workspace name cannot be blank")
    return name.strip()


def _valid_key(key):
    if not key or len(key) > 120:
        raise HTTPException(422, "Idempotency-Key must be 1 to 120 characters")
    return key


def create_app(database_path=None):
    app = FastAPI(title="CLARVIO Workspace API", version="0.1.0")
    app.state.store = WorkspaceStore(database_path)
    app.mount("/static", StaticFiles(directory=WEB), name="static")

    @app.exception_handler(NotFound)
    async def not_found(_request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(VersionConflict)
    @app.exception_handler(IdempotencyConflict)
    async def conflict(_request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.get("/")
    def home():
        return FileResponse(WEB / "index.html")

    @app.get("/api/health")
    def health():
        return {"status": "ok", "schema_version": app.state.store.schema_version()}

    @app.get("/api/workspaces")
    def list_workspaces():
        return app.state.store.list()

    @app.post("/api/workspaces", status_code=201)
    def create_workspace(body: NewWorkspace, idempotency_key: str = Header(...)):
        return app.state.store.create(_valid_name(body.name), _valid_key(idempotency_key))

    @app.get("/api/workspaces/{workspace_id}")
    def get_workspace(workspace_id: str):
        return app.state.store.get(workspace_id)

    @app.put("/api/workspaces/{workspace_id}")
    def update_workspace(workspace_id: str, body: UpdateWorkspace, idempotency_key: str = Header(...)):
        return app.state.store.update(
            workspace_id, body.expected_version, _valid_name(body.name), body.summary,
            _valid_key(idempotency_key),
        )

    @app.get("/api/workspaces/{workspace_id}/versions")
    def list_versions(workspace_id: str):
        return app.state.store.versions(workspace_id)

    @app.get("/api/workspaces/{workspace_id}/versions/{version}")
    def get_version(workspace_id: str, version: int):
        return app.state.store.version(workspace_id, version)

    return app


app = create_app()
