import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.environments.servicedesk.fixtures import validate_servicedesk_fixtures
from app.models.servicedesk import Incident
from app.schemas.scenarios import ScenarioDefinition, ScenarioValidationReport

SUPPORTED_TOOL_NAMES = (
    "get_incident",
    "search_incidents",
    "update_incident",
    "assign_incident",
    "add_work_note",
    "resolve_incident",
    "get_user_permissions",
    "list_teams",
    "get_incident_history",
    "get_current_user",
)


class ScenarioValidationError(ValueError):
    """Raised when scenario definitions fail static validation."""


class ScenarioLoader:
    """Loads the versioned Service Desk scenario catalog and validates its contract."""

    def __init__(self, path: str | Path | None = None, expected_count: int = 10):
        self.path = Path(path) if path else Path(__file__).parent / "scenarios" / "v1.json"
        self.expected_count = expected_count

    def load(self) -> list[ScenarioDefinition]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ScenarioValidationError("Scenario catalog must be a JSON array")
        scenarios = [ScenarioDefinition.model_validate(item) for item in raw]
        report = self.validate(scenarios)
        if not report.passed:
            raise ScenarioValidationError("; ".join(report.errors))
        return scenarios

    def validate(self, scenarios: list[ScenarioDefinition]) -> ScenarioValidationReport:
        errors: list[str] = []
        ids = [item.scenario_id for item in scenarios]
        if len(scenarios) != self.expected_count:
            errors.append(f"Expected {self.expected_count} scenarios, found {len(scenarios)}")
        if len(ids) != len(set(ids)):
            errors.append("Scenario IDs must be unique")
        supported = set(SUPPORTED_TOOL_NAMES)
        for scenario in scenarios:
            if scenario.fixture_id != "servicedesk_v1":
                errors.append(f"{scenario.scenario_id}: unsupported fixture '{scenario.fixture_id}'")
            unknown_tools = sorted(set(scenario.allowed_tools) - supported)
            if unknown_tools:
                errors.append(f"{scenario.scenario_id}: unknown tools {unknown_tools}")
            if len(scenario.allowed_tools) != len(set(scenario.allowed_tools)):
                errors.append(f"{scenario.scenario_id}: allowed_tools contains duplicates")
            if not scenario.forbidden_side_effects:
                errors.append(f"{scenario.scenario_id}: forbidden_side_effects must not be empty")
            if scenario.expected_state.incident_number and scenario.expected_state.incident_number != scenario.target_incident_number:
                errors.append(f"{scenario.scenario_id}: expected_state incident does not match target")
        return ScenarioValidationReport(
            passed=not errors,
            total=len(scenarios),
            scenario_ids=ids,
            errors=errors,
        )


def validate_scenario_fixtures(db: Session, scenarios: list[ScenarioDefinition]) -> ScenarioValidationReport:
    """Validate scenario preconditions against a freshly seeded v1 simulator fixture."""
    loader = ScenarioLoader(expected_count=10)
    static_report = loader.validate(scenarios)
    fixture_report = validate_servicedesk_fixtures(db, require_clean=True)
    errors = list(static_report.errors)
    if not fixture_report.passed:
        errors.extend(f"fixture:{check.key}" for check in fixture_report.checks if not check.passed)

    for scenario in scenarios:
        for precondition in scenario.preconditions:
            incident = db.scalar(select(Incident).where(func.upper(Incident.number) == precondition.incident_number.upper()))
            if incident is None:
                errors.append(f"{scenario.scenario_id}: precondition incident {precondition.incident_number} is missing")
                continue
            actuals = {
                "state": incident.state,
                "priority": incident.priority,
                "assignment_group": incident.assignment_group.name if incident.assignment_group else None,
                "assigned_to": incident.assigned_to.username if incident.assigned_to else None,
            }
            for key, expected in {
                "state": precondition.state,
                "priority": precondition.priority,
                "assignment_group": precondition.assignment_group,
                "assigned_to": precondition.assigned_to,
            }.items():
                if expected is not None and actuals[key] != expected:
                    errors.append(f"{scenario.scenario_id}: {precondition.incident_number} {key} expected {expected!r}, got {actuals[key]!r}")

        if scenario.expected_state.found is False:
            exists = db.scalar(select(Incident.id).where(func.upper(Incident.number) == scenario.target_incident_number.upper())) is not None
            if exists:
                errors.append(f"{scenario.scenario_id}: expected missing incident {scenario.target_incident_number} exists in fixture")
        elif scenario.expected_state.found is True:
            exists = db.scalar(select(Incident.id).where(func.upper(Incident.number) == scenario.target_incident_number.upper())) is not None
            if not exists:
                errors.append(f"{scenario.scenario_id}: expected incident {scenario.target_incident_number} is missing from fixture")

    return ScenarioValidationReport(
        passed=not errors,
        total=static_report.total,
        scenario_ids=static_report.scenario_ids,
        errors=errors,
        fixture_integrity=fixture_report,
    )
