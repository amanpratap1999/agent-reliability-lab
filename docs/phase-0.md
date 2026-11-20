# Phase 0 — Foundation

## Scope
FastAPI, Pydantic v2, SQLAlchemy, SQLite, Alembic, project CRUD, health checks, tests and CI. Simulator, adapters, execution, tracing, evaluation, safety and dashboard belong to later phases.

## API
Liveness: `GET /health/live` (process only). Readiness: `GET /health/ready` (database connectivity). Project endpoints under `/api/v1`: `POST /projects`, `GET /projects`, `GET /projects/{project_id}`, `PATCH /projects/{project_id}`, `POST /projects/{project_id}/archive`.

Archived projects are excluded from the default list; use `?include_archived=true` to include them. IDs are UUID strings. Names are trimmed and cannot be blank.

## Database
Default: `sqlite:///./agent_reliability_lab.db`, relative to the backend working directory. Override with `DATABASE_URL`. Schema is managed by Alembic; the app does not silently create tables on startup.

## Remote verification
GitHub Actions runs pytest and `alembic upgrade head` on Ubuntu with Python 3.11. A green workflow run is evidence that those commands executed successfully. A commit alone is not a test result.

## Current limitations
No authentication, tenancy, agent execution, simulator or benchmark data in Phase 0. No secrets are accepted or persisted. SQLite is the initial store; changing it requires an explicit design decision.
