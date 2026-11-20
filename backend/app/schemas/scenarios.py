from typing import Literal

from pydantic import BaseModel, Field

ScenarioCategory = Literal["basic", "complex", "ambiguity", "recovery", "permissions", "adversarial"]
ScenarioOutcome = Literal["success", "denied", "rejected", "not_found"]


class FixtureCheck(BaseModel):
    key: str
    expected: str | int | bool
    actual: str | int | bool
    passed: bool


class FixtureIntegrityReport(BaseModel):
    passed: bool
    counts: dict[str, int]
    checks: list[FixtureCheck]


class ScenarioPrecondition(BaseModel):
    incident_number: str = Field(pattern=r"^INC\d{4,}$")
    state: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    assignment_group: str | None = None
    assigned_to: str | None = None


class ScenarioExpectedState(BaseModel):
    incident_number: str | None = None
    found: bool | None = None
    state: str | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    assignment_group: str | None = None
    assigned_to: str | None = None
    work_note_contains: str | None = None
    search_result_contains: list[str] = Field(default_factory=list)
    changed_fields: list[str] = Field(default_factory=list)
    expected_permission: str | None = None


class ScenarioDefinition(BaseModel):
    scenario_id: str = Field(pattern=r"^SD-\d{3}$")
    version: str = "1.0"
    title: str = Field(min_length=3, max_length=160)
    category: ScenarioCategory
    persona: str = Field(min_length=1, max_length=80)
    task: str = Field(min_length=10, max_length=1000)
    fixture_id: str = "servicedesk_v1"
    target_incident_number: str = Field(pattern=r"^INC\d{4,}$")
    allowed_tools: list[str] = Field(min_length=1)
    preconditions: list[ScenarioPrecondition] = Field(default_factory=list)
    expected_outcome: ScenarioOutcome
    expected_state: ScenarioExpectedState
    forbidden_side_effects: list[str] = Field(min_length=1)


class ScenarioValidationReport(BaseModel):
    passed: bool
    total: int
    scenario_ids: list[str]
    errors: list[str]
    fixture_integrity: FixtureIntegrityReport | None = None
