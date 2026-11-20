import pytest
from sqlalchemy import select

from app.core.environments.servicedesk.fixtures import IDS, reset_servicedesk
from app.core.environments.servicedesk.tools import ServiceDeskTools
from app.core.environments.servicedesk.verifier import ServiceDeskVerifier
from app.models.servicedesk import Incident
from app.schemas.servicedesk import AddWorkNoteInput, IncidentAssignmentInput


def test_verifier_reads_persisted_state_without_calling_agent_tools(db_session, monkeypatch):
    reset_servicedesk(db_session)
    tools = ServiceDeskTools(db_session, IDS["user_agent"])
    tools.assign_incident(IncidentAssignmentInput(incident_number="INC1001", assignment_group="Network Team", assigned_to="network.agent"))
    tools.add_work_note(AddWorkNoteInput(incident_number="INC1001", content="Independent verification note."))

    def agent_tool_must_not_be_called(*_args, **_kwargs):
        pytest.fail("Independent verifier must not call agent-facing tools")

    monkeypatch.setattr(ServiceDeskTools, "get_incident", agent_tool_must_not_be_called)
    monkeypatch.setattr(ServiceDeskTools, "search_incidents", agent_tool_must_not_be_called)
    verifier = ServiceDeskVerifier(db_session)
    result = verifier.verify_incident(
        "INC1001", expected_state="In Progress", expected_assignment_group="Network Team",
        expected_assigned_to="network.agent", expected_work_note="Independent verification note.",
    )
    assert result.passed is True
    assert result.observed.assignment_group == "Network Team"
    assert result.observed.assigned_to == "network.agent"


def test_verifier_detects_unrelated_record_changes(db_session):
    reset_servicedesk(db_session)
    verifier = ServiceDeskVerifier(db_session)
    before = verifier.capture_snapshot()
    ServiceDeskTools(db_session, IDS["user_agent"]).assign_incident(
        IncidentAssignmentInput(incident_number="INC1001", assignment_group="Network Team", assigned_to="network.agent")
    )
    after_target_change = verifier.capture_snapshot()
    allowed_only_target = verifier.verify_no_unrelated_changes(before, after_target_change, {"INC1001"})
    assert allowed_only_target.passed is True
    assert allowed_only_target.changed_incident_numbers == []

    unrelated = db_session.scalar(select(Incident).where(Incident.number == "INC1002"))
    unrelated.priority = 1
    db_session.commit()
    after_unrelated_change = verifier.capture_snapshot()
    detected = verifier.verify_no_unrelated_changes(before, after_unrelated_change, {"INC1001"})
    assert detected.passed is False
    assert detected.changed_incident_numbers == ["INC1002"]


def test_verifier_is_read_only_and_handles_missing_incidents(db_session):
    reset_servicedesk(db_session)
    verifier = ServiceDeskVerifier(db_session)
    before = verifier.capture_snapshot()
    result = verifier.verify_incident("INC1001", expected_state="In Progress", expected_priority=2)
    missing = verifier.verify_incident("INC9999", expected_state="New")
    after = verifier.capture_snapshot()
    assert result.passed is True
    assert missing.passed is False
    assert missing.observed is None
    assert before == after
