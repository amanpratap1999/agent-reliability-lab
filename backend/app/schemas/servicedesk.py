from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

IncidentState = Literal["New", "In Progress", "On Hold", "Resolved", "Closed"]


class IncidentLookupInput(BaseModel):
    incident_number: str = Field(pattern=r"^INC\d{4,}$", min_length=7, max_length=20)
    @field_validator("incident_number", mode="before")
    @classmethod
    def normalize_incident_number(cls, value: str) -> str:
        return str(value).strip().upper()


class IncidentSearchInput(BaseModel):
    query: str | None = Field(default=None, max_length=200)
    state: IncidentState | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    assignment_group: str | None = Field(default=None, max_length=100)
    assigned_to: str | None = Field(default=None, max_length=80)
    limit: int = Field(default=25, ge=1, le=100)


class ListTeamsInput(BaseModel):
    include_inactive: bool = False


class IncidentUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_number: str = Field(pattern=r"^INC\d{4,}$", min_length=7, max_length=20)
    short_description: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    state: IncidentState | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    @field_validator("incident_number", mode="before")
    @classmethod
    def normalize_incident_number(cls, value: str) -> str:
        return str(value).strip().upper()
    @model_validator(mode="after")
    def validate_changes(self):
        changes = self.model_dump(exclude={"incident_number"}, exclude_unset=True)
        if not changes:
            raise ValueError("At least one updatable field must be supplied")
        if any(value is None for value in changes.values()):
            raise ValueError("Updatable fields cannot be null")
        return self


class IncidentAssignmentInput(BaseModel):
    incident_number: str = Field(pattern=r"^INC\d{4,}$", min_length=7, max_length=20)
    assignment_group: str = Field(min_length=1, max_length=100)
    assigned_to: str | None = Field(default=None, max_length=80)
    @field_validator("incident_number", mode="before")
    @classmethod
    def normalize_incident_number(cls, value: str) -> str:
        return str(value).strip().upper()
    @field_validator("assignment_group")
    @classmethod
    def normalize_assignment_group(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Assignment group cannot be blank")
        return value
    @field_validator("assigned_to")
    @classmethod
    def normalize_assignee(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Assignee cannot be blank; use null to clear")
        return value


class AddWorkNoteInput(BaseModel):
    incident_number: str = Field(pattern=r"^INC\d{4,}$", min_length=7, max_length=20)
    content: str = Field(min_length=1, max_length=4000)
    @field_validator("incident_number", mode="before")
    @classmethod
    def normalize_incident_number(cls, value: str) -> str:
        return str(value).strip().upper()
    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Work note content cannot be blank")
        return value


class ResolveIncidentInput(BaseModel):
    incident_number: str = Field(pattern=r"^INC\d{4,}$", min_length=7, max_length=20)
    resolution_notes: str = Field(min_length=1, max_length=4000)
    @field_validator("incident_number", mode="before")
    @classmethod
    def normalize_incident_number(cls, value: str) -> str:
        return str(value).strip().upper()
    @field_validator("resolution_notes")
    @classmethod
    def validate_resolution_notes(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Resolution notes cannot be blank")
        return value


class IncidentHistoryInput(BaseModel):
    incident_number: str = Field(pattern=r"^INC\d{4,}$", min_length=7, max_length=20)
    since: datetime | None = None
    event_type: Literal["all", "changes", "attempts"] = "all"
    limit: int = Field(default=50, ge=1, le=100)
    @field_validator("incident_number", mode="before")
    @classmethod
    def normalize_incident_number(cls, value: str) -> str:
        return str(value).strip().upper()


class WorkNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    author: str
    content: str
    created_at: datetime


class IncidentSummary(BaseModel):
    id: str
    number: str
    short_description: str
    state: IncidentState
    priority: int
    assignment_group: str | None
    assigned_to: str | None


class IncidentDetail(IncidentSummary):
    description: str
    opened_by: str
    work_notes: list[WorkNoteRead]
    created_at: datetime
    updated_at: datetime


class IncidentLookupResult(BaseModel):
    found: bool
    incident: IncidentDetail | None


class IncidentSearchResult(BaseModel):
    items: list[IncidentSummary]
    total: int
    limit: int


class TeamRead(BaseModel):
    id: str
    name: str
    description: str | None
    is_active: bool


class TeamListResult(BaseModel):
    teams: list[TeamRead]
    total: int


class CurrentUserResult(BaseModel):
    id: str
    username: str
    display_name: str
    is_active: bool
    roles: list[str]


class UserPermissionsResult(BaseModel):
    username: str
    roles: list[str]
    permissions: list[str]


class IncidentMutationResult(BaseModel):
    success: bool
    message: str
    incident: IncidentDetail
    changed_fields: list[str]


class IncidentHistoryEvent(BaseModel):
    id: str
    source: Literal["audit", "attempt"]
    action: str
    outcome: str
    actor: str | None
    field_name: str | None = None
    previous_value: str | None = None
    new_value: str | None = None
    reason: str | None = None
    details: dict | None = None
    occurred_at: datetime


class IncidentHistoryResult(BaseModel):
    incident_number: str
    events: list[IncidentHistoryEvent]
    total: int
    limit: int
