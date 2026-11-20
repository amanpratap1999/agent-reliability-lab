from datetime import datetime

from pydantic import BaseModel


class VerifiedIncidentState(BaseModel):
    id: str
    number: str
    short_description: str
    description: str
    state: str
    priority: int
    assignment_group: str | None
    assigned_to: str | None
    opened_by: str
    work_note_contents: list[str]
    work_notes_count: int
    audit_count: int
    tool_attempt_count: int
    updated_at: datetime


class VerificationCheck(BaseModel):
    key: str
    expected: str | int | bool | None
    actual: str | int | bool | None
    passed: bool


class IncidentVerificationResult(BaseModel):
    incident_number: str
    passed: bool
    checks: list[VerificationCheck]
    observed: VerifiedIncidentState | None


class UnrelatedChangesResult(BaseModel):
    passed: bool
    allowed_incident_numbers: list[str]
    changed_incident_numbers: list[str]
    before_count: int
    after_count: int
