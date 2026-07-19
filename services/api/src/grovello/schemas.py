from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: "".join(
            [value.split("_")[0], *[part.title() for part in value.split("_")[1:]]]
        ),
        populate_by_name=True,
    )


class ApiMeta(ApiModel):
    request_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: Literal["live", "seed"] = "live"


class ApiEnvelope[EnvelopeData](ApiModel):
    data: EnvelopeData
    meta: ApiMeta


class HealthStatus(ApiModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str


class Capability(ApiModel):
    key: str
    name: str
    outcome: str
    state: Literal["foundation", "connected", "operational"]
    object_types: list[str]


class DashboardMetric(ApiModel):
    key: str
    label: str
    value: str
    delta: str


class DashboardOverview(ApiModel):
    metrics: list[DashboardMetric]
    pending_decisions: int
    active_runs: int
    data_notice: str


class WorkspaceSummary(ApiModel):
    id: str
    organization_id: str
    slug: str
    name: str
    default_locale: str
    timezone: str
    currency: str


class WorkspaceAccessSummary(ApiModel):
    workspace: WorkspaceSummary
    subject_id: str
    session_id: str
    roles: list[str]
    permissions: list[str]


class AuditEventSummary(ApiModel):
    id: str
    workspace_id: str
    actor_type: str
    actor_id: str
    session_id: str
    action: str
    resource_type: str
    resource_id: str
    outcome: str
    request_id: str
    evidence: dict


class RecoveryPlan(ApiModel):
    workspace_id: str
    status: Literal["ready", "blocked"]
    required_permission: str
    safeguards: list[str]
