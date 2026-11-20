# Day 1 — Repository and implementation baseline

**Recorded:** 2026-11-20  
**Source of truth:** GitHub repository and executed GitHub Actions evidence  
**Project specification:** [Canonical Notion blueprint](https://app.notion.com/p/41ce4c19f3db8193bc8fe404e26b9240)

## Confirmed repository facts

- Repository: `amanpratap1999/agent-reliability-lab`
- URL: https://github.com/amanpratap1999/agent-reliability-lab
- Visibility: public
- Default branch: `main`
- Connected repository permissions verified: admin, maintain, push, pull and triage
- Implementation workflow: work directly against GitHub; no user-local checkout or terminal session is required for the current delivery process
- Baseline initial commit: `452b65a68da1a6196ed13066a64e61023fd10709`
- Current implementation commit at time of baseline: `5a40d528c754d640569c2d87de5814b3140bc655`

## Confirmed implementation and toolchain

- Backend runtime target: Python 3.11
- Framework: FastAPI 0.115.12
- Validation: Pydantic 2.10.6
- Persistence: SQLAlchemy 2.0.38 with SQLite
- Migrations: Alembic 1.14.1
- Tests: pytest 8.3.4 and HTTPX 0.28.1
- CI: GitHub Actions on Ubuntu and Windows runners
- No Docker dependency and no paid API/model dependency in Phase 0

## Verified CI evidence

Workflow: [CI run #2](https://github.com/amanpratap1999/agent-reliability-lab/actions/runs/44675177451)  
Commit: `5a40d528c754d640569c2d87de5814b3140bc655`  
Overall result: **success**

| Runner | Python | Pytest | Alembic migration |
| --- | --- | --- | --- |
| Ubuntu latest | 3.11.18 | 5 passed, 1 warning | `alembic upgrade head` succeeded |
| Windows latest | 3.11.9 | 5 passed, 1 warning | `alembic upgrade head` succeeded |

The warning on both runners is a Starlette deprecation warning concerning AnyIO's `BlockingPortal` alias; it did not fail the test suite. GitHub Actions also emitted Node.js 20 deprecation notices from the selected checkout/setup actions; these are runner/action maintenance notices, not application test failures.

## Phase 0 implementation delivered

- FastAPI application and health/readiness endpoints
- Project persistence model, Pydantic contracts, repository and service layers
- Project create, list, retrieve, update and archive endpoints
- Initial Alembic migration
- Five tests covering health, project CRUD/archive, validation and missing resources
- GitHub Actions CI across Ubuntu and Windows
- README, Phase 0 notes, contributing guide, Apache-2.0 license and optional PowerShell helper scripts

## Locked constraints reaffirmed

- Modular monolith; no microservices
- SQLite initially, SQLAlchemy and Alembic
- Controlled Service Desk simulator is the first environment in a later phase
- Independent deterministic environment-state verification remains the truth source
- Safety remains separate and non-compensatory
- No hidden chain-of-thought capture
- No silent success when evidence is missing or inconclusive
- No architecture, provider, dependency, plugin or infrastructure changes without explicit approval

## Deferred / not applicable to this baseline

- Node/npm versions are deferred until the frontend phase; Phase 0 contains no Node frontend.
- No local machine state was inspected or changed; the user selected a GitHub-only implementation workflow.
- No production ServiceNow integration, external LLM provider, credentials or secrets were configured.
- Application runtime behavior is covered by API tests; a persistent hosted deployment is not part of Phase 0.

## Remaining Phase 0 review

The initial foundation and CI acceptance checks are green on both operating systems. The next engineering step is a focused code review of API behavior, migration reversibility, dependency maintenance and error handling before closing Phase 0 and beginning the Service Desk simulator phase.
