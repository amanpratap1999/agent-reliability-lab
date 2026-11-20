import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.environments.servicedesk.fixtures import IDS, fixture_counts, reset_servicedesk
from app.models.servicedesk import AuditHistory, Incident, Permission, Role, Team, User, WorkNote


def _snapshot(db_session):
    incidents = db_session.scalars(select(Incident).order_by(Incident.number)).all()
    return {
        "incidents": [(item.id, item.number, item.state, item.priority, item.assignment_group.name if item.assignment_group else None, item.assigned_to.username if item.assigned_to else None, item.opened_by.username) for item in incidents],
        "work_notes": [(item.id, item.incident_id, item.author_user_id, item.content) for item in db_session.scalars(select(WorkNote).order_by(WorkNote.id)).all()],
        "audit": [(item.id, item.incident_id, item.action, item.new_value) for item in db_session.scalars(select(AuditHistory).order_by(AuditHistory.id)).all()],
        "counts": fixture_counts(db_session),
    }


def test_fixture_reset_is_deterministic(db_session):
    first_counts = reset_servicedesk(db_session)
    first_snapshot = _snapshot(db_session)
    second_counts = reset_servicedesk(db_session)
    second_snapshot = _snapshot(db_session)
    assert first_counts == second_counts
    assert first_counts == {"teams": 2, "users": 4, "roles": 3, "permissions": 8, "incidents": 3, "work_notes": 1, "audit_history": 3, "tool_attempts": 0}
    assert first_snapshot == second_snapshot


def test_incident_relationships_and_role_permissions_are_seeded(db_session):
    reset_servicedesk(db_session)
    incident = db_session.scalar(select(Incident).where(Incident.number == "INC1001"))
    assert incident is not None
    assert incident.state == "In Progress"
    assert incident.assignment_group.name == "Service Desk"
    assert incident.assigned_to.username == "agent.user"
    assert incident.opened_by.username == "jordan.lee"
    operator = db_session.scalar(select(User).where(User.username == "agent.user"))
    assert "incident.assign" in {permission.key for role in operator.roles for permission in role.permissions}
    assert "incident.resolve" not in {permission.key for role in operator.roles for permission in role.permissions}
    assert db_session.scalar(select(Team).where(Team.name == "Network Team")) is not None
    assert db_session.scalar(select(Role).where(Role.name == "admin")) is not None
    assert db_session.scalar(select(Permission).where(Permission.key == "incident.read")) is not None


def test_foreign_keys_reject_orphaned_work_notes(db_session):
    reset_servicedesk(db_session)
    db_session.add(WorkNote(id="00000000-0000-4000-8000-000000000099", incident_id="missing-incident", author_user_id=IDS["user_agent"], content="This row must not be persisted."))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_incident_state_and_priority_constraints_are_enforced(db_session):
    reset_servicedesk(db_session)
    db_session.add(Incident(id="00000000-0000-4000-8000-000000000098", number="INC9999", short_description="Invalid priority fixture", description="Should be rejected by the database constraint.", state="New", priority=9, opened_by_user_id=IDS["user_reporter"]))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
