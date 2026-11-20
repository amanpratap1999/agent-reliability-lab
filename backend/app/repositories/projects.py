from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate

class ProjectRepository:
    def __init__(self, db: Session):
        self.db = db
    def create(self, payload: ProjectCreate) -> Project:
        project = Project(name=payload.name, description=payload.description)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project
    def list(self, include_archived: bool = False) -> list[Project]:
        statement = select(Project).order_by(Project.created_at.desc())
        if not include_archived:
            statement = statement.where(Project.is_archived.is_(False))
        return list(self.db.scalars(statement).all())
    def get(self, project_id: str) -> Project | None:
        return self.db.get(Project, project_id)
    def update(self, project: Project, payload: ProjectUpdate) -> Project:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(project, field, value)
        self.db.commit()
        self.db.refresh(project)
        return project
    def archive(self, project: Project) -> Project:
        project.is_archived = True
        self.db.commit()
        self.db.refresh(project)
        return project
