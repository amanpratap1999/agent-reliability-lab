import pytest
from sqlalchemy import select

from app.core.environments.servicedesk import (
    ScenarioLoader, ServiceDeskEnvironment, validate_scenario_fixtures,
)
from app.core.environments.servicedesk.fixtures import IDS, fixture_counts, reset_servicedesk, validate_servicedesk_fixtures
from app.core.environments.servicedesk.scenario_loader import ScenarioValidationError
from app.models.servicedesk import Incident
from app.schemas.servicedesk import (
    AddWorkNoteInput, IncidentAssignmentInput, IncidentLookupInput,
    IncidentSearchInput, IncidentUpdateInput, IncidentHistoryInput,
    ResolveIncidentInput,
)


def test_scenario_catalog_contains_ten_versioned_valid_scenarios():
    loader = ScenarioLoader()
    scenarios = loader.load()
    report = loader.validate(scenarios)
    assert len(scenarios) == 10
    assert report.passed is True
    assert len(set(report.scenario_ids)) == 10
    assert all(scenario.version == "1.0" for scenario in scenarios)


def test_scenario_catalog_rejects_unknown_tools():
    loader = ScenarioLoader()
    scenarios = loader.load()
    invalid = [item.model_copy(deep=True) for item in scenarios]
    invalid[0] = invalid[0].model_copy(update={"allowed_tools": ["made_up_tool"]})
    report = loader.validate(invalid)
    assert report.passed is False
    assert any("unknown tools" in error for error in report.errors)


def test_scenario_preconditions_match_canonical_fixture(db_session):
    reset_servicedesk(db_session)
    scenarios = ScenarioLoader().load()
    report = validate_scenario_fixtures(db_session, scenarios)
    assert report.passed is True
    assert report.total == 10
    assert report.fixture_integrity is not None
    assert report.fixture_integrity.passed is True


def test_scenario_validation_detects_fixture_drift(db_session):
    reset_servicedesk(db_session)
    incident = db_session.scalar(select(Incident).where(Incident.number == "INC1001"))
    incident.state = "On Hold"
    db_session.commit()
    report = validate_scenario_fixtures(db_session, ScenarioLoader().load())
    assert report.passed is False
    assert any("state expected 'In Progress'" in error for error in report.errors)


def test_fixture_integrity_detects_missing_seed_record(db_session):
    reset_servicedesk(db_session)
    incident = db_session.scalar(select(Incident).where(Incident.number == "INC1003"))
    db_session.delete(incident)
    db_session.commit()
    report = validate_servicedesk_fixtures(db_session)
    assert report.passed is False
    assert any(check.key == "count.incidents" and not check.passed for check in report.checks)


def test_environment_reset_is_repeatable_and_exposes_tools_and_verifier(db_session):
    environment = ServiceDeskEnvironment(db_session, IDS["user_agent"])
    first = environment.reset()
    first_counts = fixture_counts(db_session)
    environment.tools.update_incident(IncidentUpdateInput(incident_number="INC1001", priority=1))
    second = environment.reset()
    second_counts = fixture_counts(db_session)
    assert first.passed is True
    assert second.passed is True
    assert first_counts == second_counts
    assert second_counts["tool_attempts"] == 0
    assert environment.verifier.inspect_incident("INC1001").priority == 2


def test_all_ten_service_desk_tools_work_through_environment(db_session):
    environment = ServiceDeskEnvironment(db_session, IDS["user_agent"])
    environment.reset()
    tools = environment.tools
    assert tools.get_current_user().username == "agent.user"
    assert "incident.update" in tools.get_user_permissions().permissions
    assert tools.list_teams().total == 2
    assert tools.get_incident(IncidentLookupInput(incident_number="INC1001")).found is True
    assert tools.search_incidents(IncidentSearchInput(state="New")).total == 1
    assert tools.get_incident_history(IncidentHistoryInput(incident_number="INC1001")).total == 1

    tools.update_incident(IncidentUpdateInput(incident_number="INC1001", priority=1))
    tools.assign_incident(IncidentAssignmentInput(incident_number="INC1001", assignment_group="Network Team", assigned_to="network.agent"))
    tools.add_work_note(AddWorkNoteInput(incident_number="INC1001", content="Phase one tool contract verified."))
    admin_tools = ServiceDeskEnvironment(db_session, IDS["user_admin"]).tools
    admin_tools.resolve_incident(ResolveIncidentInput(incident_number="INC1001", resolution_notes="Phase one end-to-end tool smoke completed."))

    verified = environment.verifier.verify_incident(
        "INC1001", expected_state="Resolved", expected_priority=1,
        expected_assignment_group="Network Team", expected_assigned_to="network.agent",
        expected_work_note="Phase one end-to-end tool smoke completed.",
    )
    assert verified.passed is True
