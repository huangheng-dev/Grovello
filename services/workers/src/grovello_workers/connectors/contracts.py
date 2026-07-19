from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ConnectorCapability(StrEnum):
    DISCOVER = "discover"
    READ = "read"
    CREATE_DRAFT = "create_draft"
    PUBLISH = "publish"
    SEND = "send"
    UPDATE = "update"
    DELETE = "delete"
    METRICS = "metrics"


class ConnectorRisk(StrEnum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    EXTERNAL_WRITE = "external_write"
    FINANCIAL = "financial"
    DESTRUCTIVE = "destructive"


class ConnectorManifest(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    version: str
    display_name: str
    provider: str
    capabilities: set[ConnectorCapability]
    risks: set[ConnectorRisk]
    supports_webhooks: bool = False
    supports_idempotency: bool = False
    configuration_schema: dict[str, Any] = Field(default_factory=dict)


class ConnectorContext(BaseModel):
    workspace_id: str
    actor_id: str
    run_id: str
    idempotency_key: str
    locale: str = "en"
    dry_run: bool = True
    approved: bool = False
    policy_evidence: dict[str, Any] = Field(default_factory=dict)


class ConnectorResult(BaseModel):
    succeeded: bool
    external_id: str | None = None
    retryable: bool = False
    data: dict[str, Any] = Field(default_factory=dict)
    audit_evidence: dict[str, Any] = Field(default_factory=dict)


class Connector(ABC):
    """Provider-neutral boundary. Secrets are references, never method arguments or model context."""

    manifest: ConnectorManifest

    @abstractmethod
    async def health(self) -> ConnectorResult:
        """Return connection health without changing external state."""

    @abstractmethod
    async def execute(
        self,
        capability: ConnectorCapability,
        payload: dict[str, Any],
        context: ConnectorContext,
    ) -> ConnectorResult:
        """Execute one capability after authorization, policy, consent, and approval checks."""

    def validate_execution(self, capability: ConnectorCapability, context: ConnectorContext) -> None:
        if capability not in self.manifest.capabilities:
            raise ValueError(f"Connector {self.manifest.key} does not support {capability}")
        high_risk = {ConnectorRisk.EXTERNAL_WRITE, ConnectorRisk.FINANCIAL, ConnectorRisk.DESTRUCTIVE}
        if self.manifest.risks & high_risk and not context.dry_run and not context.approved:
            raise PermissionError("High-risk connector execution requires recorded approval")
