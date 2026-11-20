import pytest
from sqlalchemy import func, select

from app.core.environments.servicedesk.fixtures import IDS, reset_servicedesk
from app.core.environments.servicedesk.tools import ServiceDeskTools, ToolAuthenticationError, ToolPermissionError
from app.models.servicedesk import AuditHistory, Incident, WorkNote
from app.schemas.servicedesk import IncidentLookupInput, IncidentSearchInput, ListTeamsInput


def test_get_incident_returns_typed_detail_and_notes(db_session):
    reset_servicedesk(db_session)
    tools = ServiceDeskTools(db_session, IDS["user_agent"])
    result = tools.get_incident(IncidentLookupInput(incident_number="inc1002"))
    assert result.found is True
    assert result.incident.number == "INC1002"
    assert result.incident.assignment_group == "Service Desk"
    assert result.incident.work_notes[0].author == "agent.user"


def test_get_incident_returns_explicit_not_found(db_session):
    reset_servicedesk(db_session)
    result = ServiceDeskTools(db_session, IDS["user_agent"]).get_incident(IncidentLookupInput(incident_number="INC9999"))
    assert result.found is False
    assert result.incident is None


def test_search_incidents_filters_and_sorts_deterministically(db_session):
    reset_servicedesk(db_session)
    tools = ServiceDeskTools(db_session, IDS["user_agent"])
    result = tools.search_incidents(IncidentSearchInput(state="In Progress", assignment_group="service desk"))
    assert result.total == 1
    assert [item.number for item in result.items] == ["INC1001"]
    network_results = tools.search_incidents(IncidentSearchInput(query="network", limit=10))
    assert [item.number for item in network_results.items] == ["INC1001"]


def test_list_teams_and_current_user_are_permission_aware(db_session):
    reset_servicedesk(db_session)
    tools = ServiceDeskTools(db_session, IDS["user_agent"])
    teams = tools.list_teams(ListTeamsInput())
    assert [team.name for team in teams.teams] == ["Network Team", "Service Desk"]
    current = tools.get_current_user()
    assert current.username == "agent.user"
    assert current.roles == ["itil_user"]


def test_get_user_permissions_returns_only_current_users_grants(db_session):
    reset_servicedesk(db_session)
    result = ServiceDeskTools(db_session, IDS["user_agent"]).get_user_permissions()
    assert result.username == "agent.user"
    assert "incident.assign" in result.permissions
    assert "incident.resolve" not in result.permissions


def test_read_tools_deny_users_without_required_permissions(db_session):
    reset_servicedesk(db_session)
    tools = ServiceDeskTools(db_session, IDS["user_reporter"])
    with pytest.raises(ToolPermissionError, match="incident.read"):
        tools.get_incident(IncidentLookupInput(incident_number="INC1001"))
    with pytest.raises(ToolPermissionError, match="team.list"):
        tools.list_teams()
    with pytest.raises(ToolPermissionError, match="user.permissions.read"):
        tools.get_user_permissions()


def test_inactive_or_unknown_context_user_is_rejected(db_session):
    reset_servicedesk(db_session)
    with pytest.raises(ToolAuthenticationError):
        ServiceDeskTools(db_session, "unknown-user").get_current_user()


def test_read_operations_do_not_mutate_simulator_state(db_session):
    reset_servicedesk(db_session)
    before_incidents = db_session.scalar(select(func.count(Incident.id)))
    before_notes = db_session.scalar(select(func.count(WorkNote.id)))
    before_audit = db_session.scalar(select(func.count(AuditHistory.id)))
    tools = ServiceDeskTools(db_session, IDS["user_agent"])
    tools.get_incident(IncidentLookupInput(incident_number="INC1001"))
    tools.search_incidents(IncidentSearchInput(query="network"))
    tools.list_teams()
    tools.get_current_user()
    tools.get_user_permissions()
    assert db_session.scalar(select(func.count(Incident.id))) == before_incidents
    assert db_session.scalar(select(func.count(WorkNote.id))) == before_notes
    assert db_session.scalar(select(func.count(AuditHistory.id))) == before_audit


def test_read_input_validation_rejects_invalid_incident_numbers_and_limits():
    with pytest.raises(ValueError):
        IncidentLookupInput(incident_number="1001")
    with pytest.raises(ValueError):
        IncidentSearchInput(limit=1000)
