"""Add append-only tool attempt events."""
from alembic import op
import sqlalchemy as sa

revision = "0003_create_tool_attempts"
down_revision = "0002_create_servicedesk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sd_tool_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("sd_incidents.id", ondelete="CASCADE"), nullable=True),
        sa.Column("incident_number", sa.String(20), nullable=True),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("sd_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(200), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("outcome IN ('started', 'succeeded', 'denied', 'rejected', 'not_found', 'failed')", name="ck_sd_tool_attempts_outcome"),
    )
    op.create_index("ix_sd_tool_attempts_incident_id", "sd_tool_attempts", ["incident_id"])
    op.create_index("ix_sd_tool_attempts_incident_number", "sd_tool_attempts", ["incident_number"])
    op.create_index("ix_sd_tool_attempts_attempted_at", "sd_tool_attempts", ["attempted_at"])


def downgrade() -> None:
    op.drop_index("ix_sd_tool_attempts_attempted_at", table_name="sd_tool_attempts")
    op.drop_index("ix_sd_tool_attempts_incident_number", table_name="sd_tool_attempts")
    op.drop_index("ix_sd_tool_attempts_incident_id", table_name="sd_tool_attempts")
    op.drop_table("sd_tool_attempts")
