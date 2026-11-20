from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

user_roles = Table(
    "sd_user_roles", Base.metadata,
    Column("user_id", String(36), ForeignKey("sd_users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("sd_roles.id", ondelete="CASCADE"), primary_key=True),
)
role_permissions = Table(
    "sd_role_permissions", Base.metadata,
    Column("role_id", String(36), ForeignKey("sd_roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("sd_permissions.id", ondelete="CASCADE"), primary_key=True),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Team(Base):
    __tablename__ = "sd_teams"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    incidents: Mapped[list[Incident]] = relationship(back_populates="assignment_group")


class User(Base):
    __tablename__ = "sd_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, back_populates="users")


class Role(Base):
    __tablename__ = "sd_roles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, back_populates="roles")


class Permission(Base):
    __tablename__ = "sd_permissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    roles: Mapped[list[Role]] = relationship(secondary=role_permissions, back_populates="permissions")


class Incident(Base):
    __tablename__ = "sd_incidents"
    __table_args__ = (
        CheckConstraint("priority >= 1 AND priority <= 5", name="ck_sd_incidents_priority_range"),
        CheckConstraint("state IN ('New', 'In Progress', 'On Hold', 'Resolved', 'Closed')", name="ck_sd_incidents_state_values"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    short_description: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="New", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    assignment_group_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sd_teams.id", ondelete="RESTRICT"), nullable=True, index=True)
    assigned_to_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sd_users.id", ondelete="SET NULL"), nullable=True)
    opened_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("sd_users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
    assignment_group: Mapped[Team | None] = relationship(back_populates="incidents")
    assigned_to: Mapped[User | None] = relationship(foreign_keys=[assigned_to_user_id])
    opened_by: Mapped[User] = relationship(foreign_keys=[opened_by_user_id])
    work_notes: Mapped[list[WorkNote]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    history: Mapped[list[AuditHistory]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    tool_attempts: Mapped[list[ToolAttempt]] = relationship(back_populates="incident", cascade="all, delete-orphan")


class WorkNote(Base):
    __tablename__ = "sd_work_notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("sd_incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("sd_users.id", ondelete="RESTRICT"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    incident: Mapped[Incident] = relationship(back_populates="work_notes")
    author: Mapped[User] = relationship()


class AuditHistory(Base):
    __tablename__ = "sd_audit_history"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey("sd_incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("sd_users.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    incident: Mapped[Incident] = relationship(back_populates="history")
    actor: Mapped[User] = relationship()


class ToolAttempt(Base):
    """Append-only record of a write tool invocation and its final outcome."""
    __tablename__ = "sd_tool_attempts"
    __table_args__ = (CheckConstraint("outcome IN ('started', 'succeeded', 'denied', 'rejected', 'not_found', 'failed')", name="ck_sd_tool_attempts_outcome"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    incident_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sd_incidents.id", ondelete="CASCADE"), nullable=True, index=True)
    incident_number: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sd_users.id", ondelete="SET NULL"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    incident: Mapped[Incident | None] = relationship(back_populates="tool_attempts")
    actor: Mapped[User | None] = relationship()
