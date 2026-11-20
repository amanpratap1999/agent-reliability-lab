import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.servicedesk import (
    AuditHistory,
    Incident,
    Permission,
    Role,
    Team,
    User,
    WorkNote,
    role_permissions,
    user_roles,
)

FIXTURE_TIME = datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc)

IDS = {
    "team_service_desk": "00000000-0000-4000-8000-000000000001",
    "team_network": "00000000-0000-4000-8000-000000000002",
    "user_agent": "00000000-0000-4000-8000-000000000010",
    "user_admin": "00000000-0000-4000-8000-000000000011",
    "user_network": "00000000-0000-4000-8000-000000000012",
    "user_reporter": "00000000-0000-4000-8000-000000000013",
    "role_itil": "00000000-0000-4000-8000-000000000020",
    "role_admin": "00000000-0000-4000-8000-000000000021",
    "role_network": "00000000-0000-4000-8000-000000000022",
    "incident_1001": "00000000-0000-4000-8000-000000000040",
    "incident_1002": "00000000-0000-4000-8000-000000000041",
    "incident_1003": "00000000-0000-4000-8000-000000000042",
    "note_1002": "00000000-0000-4000-8000-000000000050",
}

PERMISSION_KEYS = (
    "incident.read",
    "incident.update",
    "incident.assign",
    "incident.work_note.add",
    "incident.resolve",
    "incident.history.read",
    "team.list",
    "user.permissions.read",
)


def reset_servicedesk(db: Session) -> dict[str, int]:
    """Replace simulator rows with a stable, known fixture state."""
    db.execute(delete(user_roles))
    db.execute(delete(role_permissions))
    for model in (AuditHistory, WorkNote, Incident, Permission, Role, User, Team):
        db.execute(delete(model))
    db.flush()
    db.expunge_all()

    teams = {
        "Service Desk": Team(id=IDS["team_service_desk"], name="Service Desk", description="Initial incident intake team"),
        "Network Team": Team(id=IDS["team_network"], name="Network Team", description="Network operations and connectivity"),
    }
    users = {
        "agent.user": User(id=IDS["user_agent"], username="agent.user", display_name="Sample ITIL Agent", email="agent.user@example.test"),
        "admin.user": User(id=IDS["user_admin"], username="admin.user", display_name="Sample Administrator", email="admin.user@example.test"),
        "network.agent": User(id=IDS["user_network"], username="network.agent", display_name="Network Engineer", email="network.agent@example.test"),
        "jordan.lee": User(id=IDS["user_reporter"], username="jordan.lee", display_name="Jordan Lee", email="jordan.lee@example.test"),
    }
    roles = {
        "itil_user": Role(id=IDS["role_itil"], name="itil_user", description="Standard service desk operator"),
        "admin": Role(id=IDS["role_admin"], name="admin", description="Simulator administrator"),
        "network_agent": Role(id=IDS["role_network"], name="network_agent", description="Network support operator"),
    }
    permissions = {
        key: Permission(
            id=f"00000000-0000-4000-8000-{0x30 + index:012d}",
            key=key,
            description=f"Permission to {key.replace('.', ' ')}",
        )
        for index, key in enumerate(PERMISSION_KEYS)
    }

    roles["itil_user"].permissions = [permissions[key] for key in (
        "incident.read", "incident.update", "incident.assign", "incident.work_note.add",
        "incident.history.read", "team.list", "user.permissions.read",
    )]
    roles["admin"].permissions = list(permissions.values())
    roles["network_agent"].permissions = [permissions[key] for key in (
        "incident.read", "incident.work_note.add", "incident.history.read", "team.list",
    )]
    users["agent.user"].roles = [roles["itil_user"]]
    users["admin.user"].roles = [roles["admin"]]
    users["network.agent"].roles = [roles["network_agent"]]

    db.add_all([*teams.values(), *users.values(), *roles.values(), *permissions.values()])
    db.flush()

    incidents = [
        Incident(
            id=IDS["incident_1001"], number="INC1001",
            short_description="Network connectivity issue in Building A",
            description="Users in Building A report intermittent network connectivity.",
            state="In Progress", priority=2, assignment_group=teams["Service Desk"],
            assigned_to=users["agent.user"], opened_by=users["jordan.lee"],
            created_at=FIXTURE_TIME, updated_at=FIXTURE_TIME,
        ),
        Incident(
            id=IDS["incident_1002"], number="INC1002",
            short_description="Email delivery delay",
            description="Outbound email delivery is slower than expected.",
            state="New", priority=3, assignment_group=teams["Service Desk"],
            assigned_to=None, opened_by=users["jordan.lee"],
            created_at=FIXTURE_TIME + timedelta(minutes=5), updated_at=FIXTURE_TIME + timedelta(minutes=5),
        ),
        Incident(
            id=IDS["incident_1003"], number="INC1003",
            short_description="VPN authentication failure",
            description="A remote user cannot complete VPN authentication.",
            state="On Hold", priority=2, assignment_group=teams["Network Team"],
            assigned_to=users["network.agent"], opened_by=users["jordan.lee"],
            created_at=FIXTURE_TIME + timedelta(minutes=10), updated_at=FIXTURE_TIME + timedelta(minutes=10),
        ),
    ]
    db.add_all(incidents)
    db.add(WorkNote(
        id=IDS["note_1002"], incident=incidents[1], author=users["agent.user"],
        content="Initial triage started; monitoring delivery queue.",
        created_at=FIXTURE_TIME + timedelta(minutes=6),
    ))
    db.add_all([
        AuditHistory(
            id=f"00000000-0000-4000-8000-{0x60 + index:012d}",
            incident=incident, actor=users["agent.user"], action="incident.created",
            new_value=json.dumps({"number": incident.number, "state": incident.state}, sort_keys=True),
            occurred_at=incident.created_at,
        )
        for index, incident in enumerate(incidents)
    ])
    db.commit()
    return fixture_counts(db)


def fixture_counts(db: Session) -> dict[str, int]:
    """Return deterministic row counts for fixture verification."""
    models = {
        "teams": Team,
        "users": User,
        "roles": Role,
        "permissions": Permission,
        "incidents": Incident,
        "work_notes": WorkNote,
        "audit_history": AuditHistory,
    }
    return {name: int(db.scalar(select(func.count()).select_from(model)) or 0) for name, model in models.items()}
