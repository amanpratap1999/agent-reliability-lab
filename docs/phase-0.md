# Phase 0 — Foundation

## Scope
FastAPI, Pydantic v2, SQLAlchemy, SQLite, Alembic, project CRUD, health checks, typed configuration, structured secret-safe logging, tests and CI. Simulator, adapters, execution, tracing, evaluation, safety and dashboard belong to later phases.

## API
Liveness: `GET /health/live` (process only). Readiness: `GET /health/ready` (database connectivity; returns 503 when the database check fails). Project endpoints under `/api/v1`: `POST /projects`, `GET /projects`, `GET /projects/{project_id}`, `PATCH /projects/{project_id}`, `POST /projects/{project_id}/archive`.

Archived projects are excluded from the default list; use `?include_archived=true` to include them. IDs are UUID strings. Names are trimmed and cannot be blank; a project name cannot be cleared with `null`.

## Configuration
Environment variables: `APP_NAME`, `APP_ENV`, `API_V1_PREFIX`, `DATABASE_URL`, `LOG_LEVEL` and `ARTIFACT_DIR`. Defaults are deterministic and do not require model credentials. Log levels are validated; log messages are JSON formatted and common authorization/token/password/secret patterns are redacted before output.

## Database
Default: `sqlite:///./agent_reliability_lab.db`, relative to the backend working directory. Override with `DATABASE_URL`. Schema is managed by Alembic; the app does not silently create tables on startup.

## Run natively on Windows
From the repository root in PowerShell:

```powershell
.\scripts\setup_windows.ps1
.\scripts\run_backend.ps1
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation. In a second PowerShell session, run tests with:

```powershell
.\scripts\run_tests.ps1
```

## Run from a Unix-like shell
From the repository root:

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

In another shell (with the virtual environment activated):

```bash
cd backend
pytest
```

## Remote verification
GitHub Actions runs pytest, `alembic upgrade head`, and a real Uvicorn startup smoke test on Ubuntu and Windows with Python 3.11. The smoke test checks both liveness and database readiness over HTTP. A green workflow run is evidence that those commands executed successfully. A commit alone is not a test result.

## Current limitations
No authentication, tenancy, agent execution, simulator or benchmark data in Phase 0. No secrets are accepted or persisted by this foundation. Redaction covers common key/value patterns, not arbitrary secret discovery. SQLite is the initial store; changing it requires an explicit design decision.
