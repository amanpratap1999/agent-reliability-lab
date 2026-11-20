from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.servicedesk import Incident, Team, User
from app.schemas.servicedesk import (
    CurrentUserResult,
    IncidentDetail,
    IncidentLookupInput,
    IncidentLookupResult,
    IncidentSearchInput,
    IncidentSearchResult,
    IncidentSummary,
    ListTeamsInput,
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


class ServiceDeskTools:
    """Typed, read-only Service Desk operations for one authenticated user context."""

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
        return any(
            permission.key == permission_key
            for role in user.roles
            for permission in role.permissions
        )

    def _require_permission(self, user: User, permission_key: str) -> None:
        if not self._has_permission(user, permission_key):
            raise ToolPermissionError(permission_key)

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
                WorkNoteRead(
                    id=note.id,
                    author=note.author.username,
                    content=note.content,
                    created_at=note.created_at,
                )
                for note in sorted(incident.work_notes, key=lambda item: (item.created_at, item.id))
            ],
            created_at=incident.created_at,
            updated_at=incident.updated_at,
        )

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
            filters.append(or_(
                Incident.number.ilike(term),
                Incident.short_description.ilike(term),
                Incident.description.ilike(term),
            ))
        if payload.state:
            filters.append(Incident.state == payload.state)
        if payload.priority is not None:
            filters.append(Incident.priority == payload.priority)
        if payload.assignment_group:
            filters.append(Incident.assignment_group.has(Team.name.ilike(payload.assignment_group.strip())))
        if payload.assigned_to:
            filters.append(Incident.assigned_to.has(User.username.ilike(payload.assigned_to.strip())))

        total = self.db.scalar(select(func.count(Incident.id)).where(*filters)) or 0
        incidents = self.db.scalars(
            select(Incident).where(*filters).order_by(Incident.number.asc()).limit(payload.limit)
        ).all()
        return IncidentSearchResult(
            items=[self._summary(incident) for incident in incidents],
            total=int(total),
            limit=payload.limit,
        )

    def list_teams(self, payload: ListTeamsInput | None = None) -> TeamListResult:
        user = self._current_user()
        self._require_permission(user, "team.list")
        options = payload or ListTeamsInput()
        statement = select(Team).order_by(Team.name.asc())
        if not options.include_inactive:
            statement = statement.where(Team.is_active.is_(True))
        teams = self.db.scalars(statement).all()
        return TeamListResult(
            teams=[TeamRead(id=team.id, name=team.name, description=team.description, is_active=team.is_active) for team in teams],
            total=len(teams),
        )

    def get_current_user(self) -> CurrentUserResult:
        user = self._current_user()
        return CurrentUserResult(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_active=user.is_active,
            roles=sorted(role.name for role in user.roles),
        )

    def get_user_permissions(self) -> UserPermissionsResult:
        user = self._current_user()
        self._require_permission(user, "user.permissions.read")
        roles = sorted(user.roles, key=lambda role: role.name)
        permission_keys = sorted({permission.key for role in roles for permission in role.permissions})
        return UserPermissionsResult(
            username=user.username,
            roles=[role.name for role in roles],
            permissions=permission_keys,
        )
