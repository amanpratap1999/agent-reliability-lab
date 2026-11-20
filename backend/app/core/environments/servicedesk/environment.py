from sqlalchemy.orm import Session

from app.core.environments.servicedesk.fixtures import reset_servicedesk, validate_servicedesk_fixtures
from app.core.environments.servicedesk.tools import ServiceDeskTools
from app.core.environments.servicedesk.verifier import ServiceDeskVerifier
from app.schemas.scenarios import FixtureIntegrityReport


class FixtureIntegrityError(RuntimeError):
    """Raised when the canonical simulator fixture fails its integrity checks."""


class ServiceDeskEnvironment:
    """Owns reset, tool context and independent verifier for one simulator session."""

    def __init__(self, db: Session, current_user_id: str):
        self.db = db
        self.current_user_id = current_user_id

    @property
    def tools(self) -> ServiceDeskTools:
        return ServiceDeskTools(self.db, self.current_user_id)

    @property
    def verifier(self) -> ServiceDeskVerifier:
        return ServiceDeskVerifier(self.db)

    def reset(self) -> FixtureIntegrityReport:
        reset_servicedesk(self.db)
        report = validate_servicedesk_fixtures(self.db, require_clean=True)
        if not report.passed:
            failed = ", ".join(check.key for check in report.checks if not check.passed)
            raise FixtureIntegrityError(f"Service Desk fixture integrity failed: {failed}")
        return report
