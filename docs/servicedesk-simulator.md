# Service Desk Simulator — Tool and Environment Contract

**Version:** v1  
**Status:** Phase 1 implementation  
**Environment:** Controlled synthetic Service Desk simulator; not a production ServiceNow connector.

## Environment lifecycle

~~~python
from app.core.environments.servicedesk import ServiceDeskEnvironment

environment = ServiceDeskEnvironment(db_session, current_user_id="00000000-0000-4000-8000-000000000010")
integrity = environment.reset()  # resets the canonical fixture and validates it
tools = environment.tools
verifier = environment.verifier
~~~

ServiceDeskEnvironment.reset() is an explicit test/demo reset. It replaces simulator rows with the deterministic servicedesk_v1 fixture and fails closed if fixture integrity checks do not pass. Do not call it during a live scenario run.

## Canonical fixture

- Teams: Service Desk, Network Team
- Users: agent.user, admin.user, network.agent, jordan.lee
- Roles: itil_user, admin, network_agent
- Incidents:
  - INC1001 — In Progress, priority 2, Service Desk, assigned to agent.user
  - INC1002 — New, priority 3, Service Desk, unassigned
  - INC1003 — On Hold, priority 2, Network Team, assigned to network.agent
- One initial work note and one creation audit record per incident.
- IDs and fixture timestamps are fixed. Write-attempt events are cleared by an explicit reset.

## Agent-facing tool contract

| Tool | Permission | Behavior |
|---|---|---|
| get_incident | incident.read | Typed incident detail; explicit found=false for missing number |
| search_incidents | incident.read | Stable incident-number ordering; query/state/priority/team/assignee filters; limit 1–100 |
| update_incident | incident.update | Allowlisted fields only: short description, description, state (except Resolved/Closed), priority |
| assign_incident | incident.assign | Requires an active assignment group; validates optional active assignee |
| add_work_note | incident.work_note.add | Adds a note authored by the current simulator user |
| resolve_incident | incident.resolve | Only In Progress or On Hold may transition to Resolved; requires resolution note |
| get_user_permissions | user.permissions.read | Returns only the current user's role and permission grants |
| list_teams | team.list | Lists active teams by default |
| get_incident_history | incident.history.read | Merges change audit and tool-attempt events; filters by event type, since time and limit |
| get_current_user | Authenticated context | Returns current simulator identity and role names |

All inputs and outputs use Pydantic schemas. Unknown update fields, invalid priorities, invalid references, missing incidents, forbidden transitions and permission failures are explicit errors.

## Role grants

| User | Role | Important grants |
|---|---|---|
| agent.user | itil_user | Read, update, assign, add work note, read history, list teams, inspect own permissions |
| admin.user | admin | All simulator permissions, including resolve |
| network.agent | network_agent | Read, add work note, read history, list teams |
| jordan.lee | None | No operator write permissions |

agent.user deliberately does not have incident.resolve; this supports negative authorization scenarios.

## Audit and attempt evidence

- sd_audit_history records successful business-state changes.
- sd_tool_attempts records write invocation start and terminal outcome (succeeded, denied, rejected, not_found, or failed).
- Attempt metadata stores the tool name, incident reference, actor, outcome, reason code and supplied field names. It does not store raw tool argument values.
- Work-note content remains in sd_work_notes; audit metadata references the note ID and content length rather than duplicating note text.
- The service interface exposes inserts only for audit/attempt records; explicit fixture reset is the test harness lifecycle operation.

## Independent verification

ServiceDeskVerifier reads Incident, WorkNote, AuditHistory and ToolAttempt persistence directly. It does not call ServiceDeskTools or trust agent-reported results. It can inspect persisted state, verify expected field values, capture snapshots and detect changes to incidents outside an allowed set.

## Scenario catalog

backend/app/core/environments/servicedesk/scenarios/v1.json contains ten versioned scenarios (SD-001–SD-010). Each declares persona, task, fixture, allowed tools, preconditions, expected outcome/state and forbidden side effects. ScenarioLoader validates the static contract; validate_scenario_fixtures checks the preconditions against a freshly reset fixture.

## Current boundaries

This is a controlled local simulator and deterministic POC. It is not connected to production ServiceNow, does not execute an autonomous agent, and does not yet include the later MCP/browser adapter, trace collector, evaluator or dashboard phases.
