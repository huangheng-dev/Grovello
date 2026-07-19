import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="active")
    workspaces: Mapped[list["Workspace"]] = relationship(back_populates="organization")


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    default_locale: Mapped[str] = mapped_column(String(12), default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    organization: Mapped[Organization] = relationship(back_populates="workspaces")
    goals: Mapped[list["Goal"]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    external_subject: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="active")


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("workspace_id", "slug"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))


class WorkspaceMembership(TimestampMixin, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")


class Role(TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("workspace_id", "key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)


class Permission(Base):
    __tablename__ = "permissions"
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    description: Mapped[str] = mapped_column(String(255))
    risk_tier: Mapped[str] = mapped_column(String(2), default="R0")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_key: Mapped[str] = mapped_column(
        ForeignKey("permissions.key", ondelete="CASCADE"), primary_key=True
    )


class MembershipRole(Base):
    __tablename__ = "membership_roles"
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace_memberships.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)


class Policy(TimestampMixin, Base):
    __tablename__ = "policies"
    __table_args__ = (UniqueConstraint("workspace_id", "key", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    rules: Mapped[dict] = mapped_column(JSON, default=dict)


class UserSession(TimestampMixin, Base):
    __tablename__ = "user_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    identity_provider: Mapped[str] = mapped_column(String(80))
    provider_session_id_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Goal(TimestampMixin, Base):
    __tablename__ = "goals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    metric_key: Mapped[str] = mapped_column(String(100))
    target_value: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    workspace: Mapped[Workspace] = relationship(back_populates="goals")


class Run(TimestampMixin, Base):
    __tablename__ = "runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    workflow_type: Mapped[str] = mapped_column(String(120), index=True)
    workflow_id: Mapped[str] = mapped_column(String(180), unique=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str] = mapped_column(String(180))
    session_id: Mapped[str | None] = mapped_column(String(180), index=True)
    request_id: Mapped[str | None] = mapped_column(String(180), index=True)
    action: Mapped[str] = mapped_column(String(160), index=True)
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(180))
    outcome: Mapped[str] = mapped_column(String(32), default="succeeded")
    reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    aggregate_type: Mapped[str] = mapped_column(String(100), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(180), index=True)
    event_type: Mapped[str] = mapped_column(String(160), index=True)
    event_version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[dict] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
