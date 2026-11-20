from sqlalchemy.orm import Session
from app.models.project import Project
from app.repositories.projects import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectUpdate

class ProjectService:
    def __init__(self, db: Session):
        self.repository = ProjectRepository(db)
    def create(self, payload: ProjectCreate) -> Project:
        return self.repository.create(payload)
    def list(self, include_archived: bool = False) -> list[Project]:
        return self.repository.list(include_archived=include_archived)
    def get(self, project_id: str) -> Project | None:
        return self.repository.get(project_id)
    def update(self, project_id: str, payload: ProjectUpdate) -> Project | None:
        project = self.get(project_id)
        return self.repository.update(project, payload) if project else None
    def archive(self, project_id: str) -> Project | None:
        project = self.get(project_id)
        return self.repository.archive(project) if project else None
