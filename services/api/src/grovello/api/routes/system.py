from typing import Annotated

from fastapi import APIRouter, Depends, Request

from grovello.api.dependencies import get_asset_scanner, get_object_storage
from grovello.asset_scanner import AssetScanner
from grovello.config import get_settings
from grovello.object_storage import ObjectStorage
from grovello.schemas import (
    ApiEnvelope,
    ApiMeta,
    AssetScannerHealthStatus,
    Capability,
    HealthStatus,
    ObjectStorageHealthStatus,
)

router = APIRouter()
settings = get_settings()

CAPABILITIES = [
    Capability(
        key="command",
        name="Growth Command",
        outcome="Goals become governed execution plans.",
        state="foundation",
        object_types=["Goal", "Strategy", "Approval"],
    ),
    Capability(
        key="brand",
        name="Brand & Market",
        outcome="Every action uses the same verified business truth.",
        state="foundation",
        object_types=[
            "Brand",
            "Product",
            "Offer",
            "PriceBook",
            "Market",
            "ICP",
            "Evidence",
            "KnowledgeDocument",
            "Asset",
            "CaseStudy",
        ],
    ),
    Capability(
        key="content",
        name="Content & Traffic",
        outcome="Demand becomes governed, channel-native traffic assets.",
        state="foundation",
        object_types=["Brief", "Content", "Keyword", "Citation"],
    ),
    Capability(
        key="channels",
        name="Channels & Ads",
        outcome="Owned and paid distribution stays observable and controlled.",
        state="foundation",
        object_types=["ChannelAccount", "Publication", "AdCampaign"],
    ),
    Capability(
        key="pipeline",
        name="Leads & Outreach",
        outcome="Market signals become qualified, consent-aware conversations.",
        state="foundation",
        object_types=["Account", "Contact", "Lead", "Conversation"],
    ),
    Capability(
        key="revenue",
        name="Customers & Revenue",
        outcome="Qualified demand becomes contracts, orders, and revenue.",
        state="foundation",
        object_types=["Opportunity", "Quote", "Contract", "Order"],
    ),
    Capability(
        key="customer",
        name="Customer Growth",
        outcome="Delivered value becomes retention, expansion, and advocacy.",
        state="foundation",
        object_types=["CustomerHealth", "Renewal", "Referral"],
    ),
    Capability(
        key="data",
        name="Data & Intelligence",
        outcome="Actions return attributable evidence for the next decision.",
        state="foundation",
        object_types=["MetricEvent", "AttributionResult", "Experiment", "Insight"],
    ),
    Capability(
        key="automation",
        name="Automation Runtime",
        outcome="Agents execute durable, replayable, provider-neutral workflows.",
        state="foundation",
        object_types=["Agent", "Workflow", "Run", "Connector"],
    ),
    Capability(
        key="governance",
        name="Organization & Governance",
        outcome="Every human and machine action stays authorized and auditable.",
        state="foundation",
        object_types=[
            "Organization",
            "Workspace",
            "User",
            "Team",
            "Role",
            "Policy",
            "Session",
            "AuditEvent",
        ],
    ),
]


@router.get("/health", response_model=ApiEnvelope[HealthStatus])
async def health(request: Request) -> ApiEnvelope[HealthStatus]:
    return ApiEnvelope(
        data=HealthStatus(
            status="ok",
            service="grovello-api",
            version=settings.api_version,
            environment=settings.environment,
        ),
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get(
    "/object-storage/health",
    response_model=ApiEnvelope[ObjectStorageHealthStatus],
)
async def object_storage_health(
    request: Request,
    storage: Annotated[ObjectStorage | None, Depends(get_object_storage)],
) -> ApiEnvelope[ObjectStorageHealthStatus]:
    if storage is None:
        health_status = ObjectStorageHealthStatus(
            status="degraded",
            provider="s3-compatible",
            configured=False,
            detail="not_configured",
        )
    else:
        result = await storage.health()
        health_status = ObjectStorageHealthStatus(
            status="ok" if result.available else "degraded",
            provider=result.provider,
            configured=True,
            detail=result.detail,
        )
    return ApiEnvelope(
        data=health_status,
        meta=ApiMeta(request_id=request.state.request_id),
    )


@router.get(
    "/asset-scanner/health",
    response_model=ApiEnvelope[AssetScannerHealthStatus],
)
async def asset_scanner_health(
    request: Request,
    scanner: Annotated[AssetScanner | None, Depends(get_asset_scanner)],
) -> ApiEnvelope[AssetScannerHealthStatus]:
    if scanner is None:
        health_status = AssetScannerHealthStatus(
            status="degraded",
            provider="clamav",
            configured=False,
            detail="not_configured",
        )
    else:
        result = await scanner.health()
        health_status = AssetScannerHealthStatus(
            status="ok" if result.available else "degraded",
            provider=result.provider,
            configured=True,
            detail=result.detail,
        )
    return ApiEnvelope(data=health_status, meta=ApiMeta(request_id=request.state.request_id))


@router.get("/capabilities", response_model=ApiEnvelope[list[Capability]])
async def capabilities(request: Request) -> ApiEnvelope[list[Capability]]:
    return ApiEnvelope(data=CAPABILITIES, meta=ApiMeta(request_id=request.state.request_id, source="seed"))
