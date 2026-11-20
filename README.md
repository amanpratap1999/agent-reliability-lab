# Agent Reliability Lab

> Prove whether an AI agent completed a real task correctly, safely, and consistently — with evidence.

An open-source, local-first reliability engineering workbench for evaluating, observing, debugging, replaying, and regression-testing autonomous AI agents. It independently verifies environment state instead of trusting an agent's final response.

**Current phase:** Phase 0 — Foundation.  
**Canonical specification:** [Notion blueprint](https://app.notion.com/p/41ce4c19f3db8193bc8fe404e26b9240)

## Phase 0 scope
- FastAPI application, health and readiness endpoints
- SQLAlchemy persistence, SQLite and Alembic migrations
- Project create/list/get/update/archive API
- Pydantic v2 contracts, validated configuration and secret-safe structured logging
- Pytest coverage, live-server smoke test and GitHub Actions CI

Later phases are intentionally not scaffolded yet.

## Locked principles
- Modular monolith; no microservices
- Open-source-first; deterministic demo requires no paid model/API
- Independent environment-state verification is the source of truth
- Safety is separate and non-compensatory
- Capture observable actions, tool calls, outputs, timings, errors and state transitions only; never hidden chain-of-thought
- Missing or inconclusive evidence must never be presented as success
- No Docker requirement for local development

## Layout
```text
backend/app/{api,core,db,models,repositories,schemas,services}/
backend/migrations/
backend/scripts/
backend/tests/
scripts/
docs/
.github/workflows/
```

## API
Base path: `/api/v1`

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | Database readiness |
| POST | `/projects` | Create project |
| GET | `/projects` | List projects |
| GET | `/projects/{project_id}` | Retrieve project |
| PATCH | `/projects/{project_id}` | Update project |
| POST | `/projects/{project_id}/archive` | Archive project |

Interactive docs: `/docs`.

## Development and verification
Targets Python 3.11 and native execution without Docker. Exact Windows and Unix setup, migration, run and test commands are in [Phase 0 notes](docs/phase-0.md). GitHub Actions runs tests, migrations and a live Uvicorn smoke test on Ubuntu and Windows; inspect workflow runs before treating a change as verified.

## License
Apache-2.0. See [LICENSE](LICENSE).
