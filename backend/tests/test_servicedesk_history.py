from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.environments.servicedesk.fixtures import IDS, reset_servicedesk
from app.core.environments.servicedesk.tools import ServiceDeskTools, ToolPermissionError
from app.models.servicedesk import AuditHistory, Incident, ToolAttempt
from app.schemas.servicedesk import (
    AddWorkNoteInput, IncidentAssignmentInput, IncidentHistoryInput,
    IncidentUpdateInput, ResolveIncidentInput,
)


def test_history_contains_successful_changes_and_attempts(db_session):
    reset_servicedesk(db_session)
    operator = ServiceDeskTools(db_session, IDS["user_agent"])
    operator.update_incident(IncidentUpdateInput(incident_number="INC1001", priority=1))
    operator.assign_incident(IncidentAssignmentInput(incident_number="INC1001", assignment_group="Network Team", assigned_to="network.agent"))
    operator.add_work_note(AddWorkNoteInput(incident_number="INC1001", content="Switch port checked and stable."))
    ServiceDeskTools(db_session, IDS["user_admin"]).resolve_incident(ResolveIncidentInput(incident_number="INC1001", resolution_notes="Connectivity verified after repair."))

    all_history = operator.get_incident_history(IncidentHistoryInput(incident_number="INC1001"))
    assert all_history.total == 15
    assert {event.source for event in all_history.events} == {"audit", "attempt"}
    audit_history = operator.get_incident_history(IncidentHistoryInput(incident_number="INC1001", event_type="changes"))
    assert audit_history.total == 7
    assert all(event.source == "audit" for event in audit_history.events)
    assert {event.action for event in audit_history.events} >= {"incident.created", "incident.updated", "incident.assigned", "incident.work_note.add", "incident.resolved"}
    attempts = operator.get_incident_history(IncidentHistoryInput(incident_number="INC1001", event_type="attempts"))
    assert attempts.total == 8
    assert all(event.source == "attempt" for event in attempts.events)


def test_denied_write_attempt_is_recorded_without_business_state_change(db_session):
    reset_servicedesk(db_session)
    before_audit = db_session.scalar(select(func.count(AuditHistory.id)))
    reporter = ServiceDeskTools(db_session, IDS["user_reporter"])
    with pytest.raises(ToolPermissionError):
        reporter.update_incident(IncidentUpdateInput(incident_number="INC1001", priority=1))

    incident = db_session.scalar(select(Incident).where(Incident.number == "INC1001"))
    assert incident.priority == 2
    assert incident.state == "In Progress"
    assert db_session.scalar(select(func.count(AuditHistory.id))) == before_audit
    attempts = db_session.scalars(select(ToolAttempt).where(ToolAttempt.incident_id == incident.id).order_by(ToolAttempt.attempted_at)).all()
    assert [event.outcome for event in attempts] == ["started", "denied"]
    assert attempts[-1].reason == "incident.update"
    assert "priority" in attempts[-1].details
    assert "1" not in attempts[-1].details

    operator_history = ServiceDeskTools(db_session, IDS["user_agent"]).get_incident_history(
        IncidentHistoryInput(incident_number="INC1001", event_type="attempts")
    )
    assert [event.outcome for event in operator_history.events] == ["started", "denied"]
    with pytest.raises(ToolPermissionError):
        reporter.get_incident_history(IncidentHistoryInput(incident_number="INC1001"))


def test_history_limit_and_since_filters_are_applied(db_session):
    reset_servicedesk(db_session)
    operator = ServiceDeskTools(db_session, IDS["user_agent"])
    operator.update_incident(IncidentUpdateInput(incident_number="INC1001", priority=1))
    limited = operator.get_incident_history(IncidentHistoryInput(incident_number="INC1001", event_type="attempts", limit=1))
    assert limited.total == 2
    assert len(limited.events) == 1
    future = datetime.now(timezone.utc) + timedelta(days=1)
    empty = operator.get_incident_history(IncidentHistoryInput(incident_number="INC1001", since=future))
    assert empty.total == 0
    assert empty.events == []
