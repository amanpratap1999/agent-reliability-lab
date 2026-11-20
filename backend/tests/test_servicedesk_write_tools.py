import pytest
from sqlalchemy import func, select

from app.core.environments.servicedesk.fixtures import IDS, reset_servicedesk
from app.core.environments.servicedesk.tools import ServiceDeskTools, ToolInputError, ToolNotFoundError, ToolPermissionError, ToolStateError
from app.models.servicedesk import AuditHistory, Incident, WorkNote
from app.schemas.servicedesk import AddWorkNoteInput, IncidentAssignmentInput, IncidentUpdateInput, ResolveIncidentInput


def _counts(db_session):
    return {
        "incidents": db_session.scalar(select(func.count(Incident.id))),
        "notes": db_session.scalar(select(func.count(WorkNote.id))),
        "audit": db_session.scalar(select(func.count(AuditHistory.id))),
    }


def test_update_incident_uses_allowlist_and_writes_audit(db_session):
    reset_servicedesk(db_session)
    tools = ServiceDeskTools(db_session, IDS["user_agent"])
    result = tools.update_incident(IncidentUpdateInput(incident_number="INC1001", priority=1, short_description="Connectivity restored"))
    assert result.success is True
    assert result.incident.priority == 1
    assert result.incident.short_description == "Connectivity restored"
    assert set(result.changed_fields) == {"priority", "short_description"}
    assert db_session.scalar(select(func.count(AuditHistory.id))) == 5


def test_update_incident_cannot_bypass_resolution_or_change_unlisted_fields(db_session):
    reset_servicedesk(db_session)
    tools = ServiceDeskTools(db_session, IDS["user_agent"])
    before = _counts(db_session)
    with pytest.raises(ToolStateError):
        tools.update_incident(IncidentUpdateInput(incident_number="INC1001", state="Resolved"))
    with pytest.raises(ValueError):
        IncidentUpdateInput(incident_number="INC1001", assignment_group="Network Team")
    assert _counts(db_session) == before
    incident = db_session.scalar(select(Incident).where(Incident.number == "INC1001"))
    assert incident.state == "In Progress"


def test_assign_incident_validates_team_and_user_references(db_session):
    reset_servicedesk(db_session)
    tools = ServiceDeskTools(db_session, IDS["user_agent"])
    result = tools.assign_incident(IncidentAssignmentInput(incident_number="INC1001", assignment_group="Network Team", assigned_to="network.agent"))
    assert result.incident.assignment_group == "Network Team"
    assert result.incident.assigned_to == "network.agent"
    assert set(result.changed_fields) == {"assignment_group", "assigned_to"}
    before = _counts(db_session)
    with pytest.raises(ToolInputError):
        tools.assign_incident(IncidentAssignmentInput(incident_number="INC1001", assignment_group="Unknown Team"))
    with pytest.raises(ToolInputError):
        tools.assign_incident(IncidentAssignmentInput(incident_number="INC1001", assignment_group="Network Team", assigned_to="missing.user"))
    assert _counts(db_session) == before


def test_add_work_note_records_author_time_and_audit(db_session):
    reset_servicedesk(db_session)
    result = ServiceDeskTools(db_session, IDS["user_agent"]).add_work_note(AddWorkNoteInput(incident_number="INC1001", content="Checked switch port; link is stable."))
    assert result.success is True
    assert result.incident.work_notes[-1].author == "agent.user"
    assert result.incident.work_notes[-1].content == "Checked switch port; link is stable."
    assert "work_notes" in result.changed_fields
    assert db_session.scalar(select(func.count(AuditHistory.id))) == 4


def test_resolve_incident_requires_permission_and_valid_state(db_session):
    reset_servicedesk(db_session)
    before = _counts(db_session)
    with pytest.raises(ToolPermissionError, match="incident.resolve"):
        ServiceDeskTools(db_session, IDS["user_agent"]).resolve_incident(ResolveIncidentInput(incident_number="INC1001", resolution_notes="Resolved by operator"))
    assert _counts(db_session) == before
    with pytest.raises(ToolStateError):
        ServiceDeskTools(db_session, IDS["user_admin"]).resolve_incident(ResolveIncidentInput(incident_number="INC1002", resolution_notes="Cannot resolve a New incident"))
    assert _counts(db_session) == before
    resolved = ServiceDeskTools(db_session, IDS["user_admin"]).resolve_incident(ResolveIncidentInput(incident_number="INC1001", resolution_notes="Connectivity verified after switch repair."))
    assert resolved.incident.state == "Resolved"
    assert resolved.incident.work_notes[-1].content == "Connectivity verified after switch repair."
    assert set(resolved.changed_fields) == {"state", "work_notes"}


def test_unauthorized_write_attempts_have_no_state_or_audit_side_effects(db_session):
    reset_servicedesk(db_session)
    before = _counts(db_session)
    reporter = ServiceDeskTools(db_session, IDS["user_reporter"])
    with pytest.raises(ToolPermissionError, match="incident.update"):
        reporter.update_incident(IncidentUpdateInput(incident_number="INC1001", priority=1))
    with pytest.raises(ToolPermissionError, match="incident.assign"):
        reporter.assign_incident(IncidentAssignmentInput(incident_number="INC1001", assignment_group="Network Team"))
    with pytest.raises(ToolPermissionError, match="incident.work_note.add"):
        reporter.add_work_note(AddWorkNoteInput(incident_number="INC1001", content="Unauthorized note"))
    assert _counts(db_session) == before
    incident = db_session.scalar(select(Incident).where(Incident.number == "INC1001"))
    assert incident.priority == 2
    assert incident.assignment_group.name == "Service Desk"
    assert incident.state == "In Progress"


def test_write_tools_reject_missing_incident_without_side_effects(db_session):
    reset_servicedesk(db_session)
    before = _counts(db_session)
    tools = ServiceDeskTools(db_session, IDS["user_agent"])
    with pytest.raises(ToolNotFoundError):
        tools.update_incident(IncidentUpdateInput(incident_number="INC9999", priority=1))
    assert _counts(db_session) == before


def test_update_input_requires_at_least_one_non_null_allowed_field():
    with pytest.raises(ValueError):
        IncidentUpdateInput(incident_number="INC1001")
    with pytest.raises(ValueError):
        IncidentUpdateInput(incident_number="INC1001", priority=None)
