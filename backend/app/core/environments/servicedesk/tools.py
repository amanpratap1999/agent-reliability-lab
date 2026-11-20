import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.servicedesk import AuditHistory, Incident, Team, User, WorkNote
from app.schemas.servicedesk import (
    AddWorkNoteInput,
    CurrentUserResult,
    IncidentAssignmentInput,
    IncidentDetail,
    IncidentLookupInput,
    IncidentLookupResult,
    IncidentMutationResult,
    IncidentSearchInput,
    IncidentSearchResult,
    IncidentSummary,
    IncidentUpdateInput,
    ListTeamsInput,
    ResolveIncidentInput,
    TeamListResult,
    TeamRead,
    UserPermissionsResult,
    WorkNoteRead,
)


class ToolAuthenticationError(PermissionError):
    """Raised when the simulator has no active user for the tool context."""


class ToolPermissionError(PermissionError):
    """Raised when the current simulator user lacks a required permission."""

    def __init__(self, permission: str):
        self.permission = permission
        super().__init__(f"Current user lacks required permission: {permission}")


class ToolInputError(ValueError):
    """Raised when a tool argument references an invalid simulator value."""


class ToolStateError(ValueError):
    """Raised when a requested state transition is not allowed."""


class ToolNotFoundError(LookupError):
    """Raised when a write operation targets a missing simulator record."""


class ServiceDeskTools:
    """Typed Service Desk operations for one authenticated simulator user context."""

    def __init__(self, db: Session, current_user_id: str):
        self.db = db
        self.current_user_id = current_user_id

    def _current_user(self) -> User:
        user = self.db.scalar(select(User).where(User.id == self.current_user_id))
        if user is None or not user.is_active:
            raise ToolAuthenticationError("No active simulator user is available")
        return user

    @staticmethod
    def _has_permission(user: User, permission_key: str) -> bool:
        return any(permission.key == permission_key for role in user.roles for permission in role.permissions)

    def _require_permission(self, user: User, permission_key: str) -> None:
        if not self._has_permission(user, permission_key):
            raise ToolPermissionError(permission_key)

    def _get_incident(self, incident_number: str) -> Incident:
        incident = self.db.scalar(select(Incident).where(func.upper(Incident.number) == incident_number.upper()))
        if incident is None:
            raise ToolNotFoundError(f"Incident {incident_number} was not found")
        return incident

    @staticmethod
    def _summary(incident: Incident) -> IncidentSummary:
        return IncidentSummary(
            id=incident.id,
            number=incident.number,
            short_description=incident.short_description,
            state=incident.state,
            priority=incident.priority,
            assignment_group=incident.assignment_group.name if incident.assignment_group else None,
            assigned_to=incident.assigned_to.username if incident.assigned_to else None,
        )

    @classmethod
    def _detail(cls, incident: Incident) -> IncidentDetail:
        summary = cls._summary(incident)
        return IncidentDetail(
            **summary.model_dump(),
            description=incident.description,
            opened_by=incident.opened_by.username,
            work_notes=[
                WorkNoteRead(id=note.id, author=note.author.username, content=note.content, created_at=note.created_at)
                for note in sorted(incident.work_notes, key=lambda item: (item.created_at, item.id))
            ],
            created_at=incident.created_at,
            updated_at=incident.updated_at,
        )

    @staticmethod
    def _audit(
        incident: Incident,
        actor: User,
        action: str,
        occurred_at: datetime,
        field_name: str | None = None,
        previous_value: str | None = None,
        new_value: str | None = None,
        details: dict | None = None,
    ) -> AuditHistory:
        return AuditHistory(
            id=str(uuid4()),
            incident=incident,
            actor=actor,
            action=action,
            field_name=field_name,
            previous_value=previous_value,
            new_value=new_value,
            details=json.dumps(details, sort_keys=True) if details is not None else None,
            occurred_at=occurred_at,
        )

    @staticmethod
    def _mutation_result(incident: Incident, message: str, changed_fields: list[str]) -> IncidentMutationResult:
        return IncidentMutationResult(success=True, message=message, incident=ServiceDeskTools._detail(incident), changed_fields=changed_fields)

    def get_incident(self, payload: IncidentLookupInput) -> IncidentLookupResult:
        user = self._current_user()
        self._require_permission(user, "incident.read")
        number = payload.incident_number.strip().upper()
        incident = self.db.scalar(select(Incident).where(func.upper(Incident.number) == number))
        if incident is None:
            return IncidentLookupResult(found=False, incident=None)
        return IncidentLookupResult(found=True, incident=self._detail(incident))

    def search_incidents(self, payload: IncidentSearchInput) -> IncidentSearchResult:
        user = self._current_user()
        self._require_permission(user, "incident.read")
        filters = []
        if payload.query:
            term = f"%{payload.query.strip()}%"
            filters.append(or_(Incident.number.ilike(term), Incident.short_description.ilike(term), Incident.description.ilike(term)))
        if payload.state:
            filters.append(Incident.state == payload.state)
        if payload.priority is not None:
            filters.append(Incident.priority == payload.priority)
        if payload.assignment_group:
            filters.append(Incident.assignment_group.has(Team.name.ilike(payload.assignment_group.strip())))
        if payload.assigned_to:
            filters.append(Incident.assigned_to.has(User.username.ilike(payload.assigned_to.strip())))
        total = self.db.scalar(select(func.count(Incident.id)).where(*filters)) or 0
        incidents = self.db.scalars(select(Incident).where(*filters).order_by(Incident.number.asc()).limit(payload.limit)).all()
        return IncidentSearchResult(items=[self._summary(item) for item in incidents], total=int(total), limit=payload.limit)

    def list_teams(self, payload: ListTeamsInput | None = None) -> TeamListResult:
        user = self._current_user()
        self._require_permission(user, "team.list")
        options = payload or ListTeamsInput()
        statement = select(Team).order_by(Team.name.asc())
        if not options.include_inactive:
            statement = statement.where(Team.is_active.is_(True))
        teams = self.db.scalars(statement).all()
        return TeamListResult(teams=[TeamRead(id=team.id, name=team.name, description=team.description, is_active=team.is_active) for team in teams], total=len(teams))

    def get_current_user(self) -> CurrentUserResult:
        user = self._current_user()
        return CurrentUserResult(id=user.id, username=user.username, display_name=user.display_name, is_active=user.is_active, roles=sorted(role.name for role in user.roles))

    def get_user_permissions(self) -> UserPermissionsResult:
        user = self._current_user()
        self._require_permission(user, "user.permissions.read")
        roles = sorted(user.roles, key=lambda role: role.name)
        permission_keys = sorted({permission.key for role in roles for permission in role.permissions})
        return UserPermissionsResult(username=user.username, roles=[role.name for role in roles], permissions=permission_keys)

    def update_incident(self, payload: IncidentUpdateInput) -> IncidentMutationResult:
        actor = self._current_user()
        self._require_permission(actor, "incident.update")
        incident = self._get_incident(payload.incident_number)
        changes = payload.model_dump(exclude={"incident_number"}, exclude_unset=True)
        if changes.get("state") in {"Resolved", "Closed"}:
            raise ToolStateError("Use resolve_incident for resolution; direct resolution/closure is not allowed")
        now = datetime.now(timezone.utc)
        changed_fields = []
        for field, value in changes.items():
            previous = getattr(incident, field)
            if previous == value:
                continue
            setattr(incident, field, value)
            self.db.add(self._audit(incident, actor, "incident.updated", now, field, str(previous), str(value)))
            changed_fields.append(field)
        if changed_fields:
            incident.updated_at = now
            self.db.commit()
            self.db.refresh(incident)
        return self._mutation_result(incident, "Incident updated" if changed_fields else "No incident fields changed", changed_fields)

    def assign_incident(self, payload: IncidentAssignmentInput) -> IncidentMutationResult:
        actor = self._current_user()
        self._require_permission(actor, "incident.assign")
        incident = self._get_incident(payload.incident_number)
        team = self.db.scalar(select(Team).where(func.lower(Team.name) == payload.assignment_group.lower()))
        if team is None or not team.is_active:
            raise ToolInputError(f"Active assignment group '{payload.assignment_group}' was not found")

        assignee = None
        should_update_assignee = "assigned_to" in payload.model_fields_set
        if should_update_assignee and payload.assigned_to is not None:
            assignee = self.db.scalar(select(User).where(func.lower(User.username) == payload.assigned_to.lower()))
            if assignee is None or not assignee.is_active:
                raise ToolInputError(f"Active user '{payload.assigned_to}' was not found")

        now = datetime.now(timezone.utc)
        changed_fields = []
        if incident.assignment_group_id != team.id:
            previous = incident.assignment_group.name if incident.assignment_group else None
            incident.assignment_group = team
            self.db.add(self._audit(incident, actor, "incident.assigned", now, "assignment_group", previous, team.name))
            changed_fields.append("assignment_group")
        if should_update_assignee:
            previous = incident.assigned_to.username if incident.assigned_to else None
            new_assignee = assignee.username if assignee else None
            if previous != new_assignee:
                incident.assigned_to = assignee
                self.db.add(self._audit(incident, actor, "incident.assigned", now, "assigned_to", previous, new_assignee))
                changed_fields.append("assigned_to")
        if changed_fields:
            incident.updated_at = now
            self.db.commit()
            self.db.refresh(incident)
        return self._mutation_result(incident, "Incident assignment updated" if changed_fields else "Incident assignment unchanged", changed_fields)

    def add_work_note(self, payload: AddWorkNoteInput) -> IncidentMutationResult:
        actor = self._current_user()
        self._require_permission(actor, "incident.work_note.add")
        incident = self._get_incident(payload.incident_number)
        now = datetime.now(timezone.utc)
        note = WorkNote(id=str(uuid4()), incident=incident, author=actor, content=payload.content, created_at=now)
        self.db.add(note)
        self.db.add(self._audit(incident, actor, "incident.work_note.add", now, new_value=payload.content, details={"work_note_id": note.id}))
        incident.updated_at = now
        self.db.commit()
        self.db.refresh(incident)
        return self._mutation_result(incident, "Work note added", ["work_notes"])

    def resolve_incident(self, payload: ResolveIncidentInput) -> IncidentMutationResult:
        actor = self._current_user()
        self._require_permission(actor, "incident.resolve")
        incident = self._get_incident(payload.incident_number)
        if incident.state not in {"In Progress", "On Hold"}:
            raise ToolStateError(f"Incident in state '{incident.state}' cannot be resolved")
        now = datetime.now(timezone.utc)
        previous_state = incident.state
        incident.state = "Resolved"
        incident.updated_at = now
        note = WorkNote(id=str(uuid4()), incident=incident, author=actor, content=payload.resolution_notes, created_at=now)
        self.db.add(note)
        self.db.add(self._audit(incident, actor, "incident.resolved", now, "state", previous_state, "Resolved"))
        self.db.add(self._audit(incident, actor, "incident.work_note.add", now, new_value=payload.resolution_notes, details={"work_note_id": note.id, "kind": "resolution"}))
        self.db.commit()
        self.db.refresh(incident)
        return self._mutation_result(incident, "Incident resolved", ["state", "work_notes"])
