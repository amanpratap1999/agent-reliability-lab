"""Create projects table."""
from alembic import op
import sqlalchemy as sa

revision = "0001_create_projects"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("projects", sa.Column("id", sa.String(length=36), nullable=False), sa.Column("name", sa.String(length=120), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("is_archived", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_projects_name", "projects", ["name"], unique=False)

def downgrade() -> None:
    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_table("projects")
