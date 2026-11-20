from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.servicedesk import AuditHistory, Incident, ToolAttempt
from app.schemas.verifier import (
    IncidentVerificationResult,
    UnrelatedChangesResult,
    VerificationCheck,
    VerifiedIncidentState,
)


class ServiceDeskVerifier:
    """Independent, read-only inspection of persisted simulator state.

    This class intentionally queries SQLAlchemy models directly. It does not
    call ServiceDeskTools, agent adapters, or agent-reported result payloads.
    """

    def __init__(self, db: Session):
        self.db = db

    def inspect_incident(self, incident_number: str) -> VerifiedIncidentState | None:
        incident = self.db.scalar(select(Incident).where(func.upper(Incident.number) == incident_number.strip().upper()))
        if incident is None:
            return None
        notes = sorted(incident.work_notes, key=lambda item: (item.created_at, item.id))
        audit_count = int(self.db.scalar(select(func.count(AuditHistory.id)).where(AuditHistory.incident_id == incident.id)) or 0)
        attempt_count = int(self.db.scalar(select(func.count(ToolAttempt.id)).where(ToolAttempt.incident_id == incident.id)) or 0)
        return VerifiedIncidentState(
            id=incident.id,
            number=incident.number,
            short_description=incident.short_description,
            description=incident.description,
            state=incident.state,
            priority=incident.priority,
            assignment_group=incident.assignment_group.name if incident.assignment_group else None,
            assigned_to=incident.assigned_to.username if incident.assigned_to else None,
            opened_by=incident.opened_by.username,
            work_note_contents=[note.content for note in notes],
            work_notes_count=len(notes),
            audit_count=audit_count,
            tool_attempt_count=attempt_count,
            updated_at=incident.updated_at,
        )

    def capture_snapshot(self) -> list[VerifiedIncidentState]:
        incidents = self.db.scalars(select(Incident).order_by(Incident.number.asc())).all()
        return [state for incident in incidents if (state := self.inspect_incident(incident.number)) is not None]

    def verify_incident(
        self,
        incident_number: str,
        *,
        expected_state: str | None = None,
        expected_priority: int | None = None,
        expected_assignment_group: str | None = None,
        expected_assigned_to: str | None = None,
        expected_work_note: str | None = None,
    ) -> IncidentVerificationResult:
        observed = self.inspect_incident(incident_number)
        if observed is None:
            return IncidentVerificationResult(
                incident_number=incident_number,
                passed=False,
                checks=[VerificationCheck(key="exists", expected=True, actual=False, passed=False)],
                observed=None,
            )
        checks = [VerificationCheck(key="exists", expected=True, actual=True, passed=True)]
        expectations = {
            "state": expected_state,
            "priority": expected_priority,
            "assignment_group": expected_assignment_group,
            "assigned_to": expected_assigned_to,
        }
        for key, expected in expectations.items():
            if expected is None:
                continue
            actual = getattr(observed, key)
            checks.append(VerificationCheck(key=key, expected=expected, actual=actual, passed=actual == expected))
        if expected_work_note is not None:
            passed = expected_work_note in observed.work_note_contents
            checks.append(VerificationCheck(key="work_note_present", expected=expected_work_note, actual=passed, passed=passed))
        return IncidentVerificationResult(
            incident_number=observed.number,
            passed=all(check.passed for check in checks),
            checks=checks,
            observed=observed,
        )

    @staticmethod
    def verify_no_unrelated_changes(
        before: list[VerifiedIncidentState],
        after: list[VerifiedIncidentState],
        allowed_incident_numbers: set[str] | None = None,
    ) -> UnrelatedChangesResult:
        allowed = {number.upper() for number in (allowed_incident_numbers or set())}
        before_by_number = {item.number: item for item in before}
        after_by_number = {item.number: item for item in after}
        all_numbers = set(before_by_number) | set(after_by_number)
        changed = sorted(
            number for number in all_numbers
            if number.upper() not in allowed and before_by_number.get(number) != after_by_number.get(number)
        )
        return UnrelatedChangesResult(
            passed=not changed,
            allowed_incident_numbers=sorted(allowed),
            changed_incident_numbers=changed,
            before_count=len(before),
            after_count=len(after),
        )
