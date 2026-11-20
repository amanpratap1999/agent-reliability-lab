"""Create Service Desk simulator domain tables."""
from alembic import op
import sqlalchemy as sa

revision = "0002_create_servicedesk"
down_revision = "0001_create_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("sd_teams", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(100), nullable=False, unique=True), sa.Column("description", sa.Text(), nullable=True), sa.Column("is_active", sa.Boolean(), nullable=False))
    op.create_table("sd_users", sa.Column("id", sa.String(36), primary_key=True), sa.Column("username", sa.String(80), nullable=False, unique=True), sa.Column("display_name", sa.String(120), nullable=False), sa.Column("email", sa.String(200), nullable=False, unique=True), sa.Column("is_active", sa.Boolean(), nullable=False))
    op.create_table("sd_roles", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(80), nullable=False, unique=True), sa.Column("description", sa.Text(), nullable=True))
    op.create_table("sd_permissions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("key", sa.String(100), nullable=False, unique=True), sa.Column("description", sa.Text(), nullable=True))
    op.create_table("sd_user_roles", sa.Column("user_id", sa.String(36), sa.ForeignKey("sd_users.id", ondelete="CASCADE"), primary_key=True), sa.Column("role_id", sa.String(36), sa.ForeignKey("sd_roles.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("sd_role_permissions", sa.Column("role_id", sa.String(36), sa.ForeignKey("sd_roles.id", ondelete="CASCADE"), primary_key=True), sa.Column("permission_id", sa.String(36), sa.ForeignKey("sd_permissions.id", ondelete="CASCADE"), primary_key=True))
    op.create_table(
        "sd_incidents",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("number", sa.String(20), nullable=False, unique=True),
        sa.Column("short_description", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("state", sa.String(30), nullable=False), sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("assignment_group_id", sa.String(36), sa.ForeignKey("sd_teams.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("assigned_to_user_id", sa.String(36), sa.ForeignKey("sd_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("opened_by_user_id", sa.String(36), sa.ForeignKey("sd_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("priority >= 1 AND priority <= 5", name="ck_sd_incidents_priority_range"),
        sa.CheckConstraint("state IN ('New', 'In Progress', 'On Hold', 'Resolved', 'Closed')", name="ck_sd_incidents_state_values"),
    )
    op.create_index("ix_sd_incidents_state", "sd_incidents", ["state"])
    op.create_index("ix_sd_incidents_assignment_group_id", "sd_incidents", ["assignment_group_id"])
    op.create_table("sd_work_notes", sa.Column("id", sa.String(36), primary_key=True), sa.Column("incident_id", sa.String(36), sa.ForeignKey("sd_incidents.id", ondelete="CASCADE"), nullable=False), sa.Column("author_user_id", sa.String(36), sa.ForeignKey("sd_users.id", ondelete="RESTRICT"), nullable=False), sa.Column("content", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_sd_work_notes_incident_id", "sd_work_notes", ["incident_id"])
    op.create_table("sd_audit_history", sa.Column("id", sa.String(36), primary_key=True), sa.Column("incident_id", sa.String(36), sa.ForeignKey("sd_incidents.id", ondelete="CASCADE"), nullable=False), sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("sd_users.id", ondelete="RESTRICT"), nullable=False), sa.Column("action", sa.String(100), nullable=False), sa.Column("field_name", sa.String(100), nullable=True), sa.Column("previous_value", sa.Text(), nullable=True), sa.Column("new_value", sa.Text(), nullable=True), sa.Column("details", sa.Text(), nullable=True), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_sd_audit_history_incident_id", "sd_audit_history", ["incident_id"])


def downgrade() -> None:
    op.drop_index("ix_sd_audit_history_incident_id", table_name="sd_audit_history")
    op.drop_table("sd_audit_history")
    op.drop_index("ix_sd_work_notes_incident_id", table_name="sd_work_notes")
    op.drop_table("sd_work_notes")
    op.drop_index("ix_sd_incidents_assignment_group_id", table_name="sd_incidents")
    op.drop_index("ix_sd_incidents_state", table_name="sd_incidents")
    op.drop_table("sd_incidents")
    op.drop_table("sd_role_permissions")
    op.drop_table("sd_user_roles")
    op.drop_table("sd_permissions")
    op.drop_table("sd_roles")
    op.drop_table("sd_users")
    op.drop_table("sd_teams")
