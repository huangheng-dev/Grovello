import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grovello.asset_uploads import (
    AssetUploadConflictError,
    AssetUploadNotFoundError,
    AssetUploadRecord,
    UploadMutationContext,
)
from grovello.models import AssetUploadSession, AuditEvent, BusinessObject, OutboxEvent


@dataclass(frozen=True, slots=True)
class RequestAssetFinalizationCommand:
    name: str
    slug: str | None
    locale: Literal["en", "zh-CN"]
    status: Literal["draft", "active"]
    metadata: dict
    change_summary: str


@dataclass(frozen=True, slots=True)
class AssetFinalizationInput:
    workspace_id: str
    upload_session_id: str
    request_hash: str
    object_key: str
    expected_provider_version_id: str | None
    expected_content_type: str
    expected_content_length: int
    expected_sha256: str
    asset_id: str
    asset_version_id: str
    blob_id: str
    destination_object_key: str
    name: str
    slug: str | None
    locale: str
    status: str
    metadata: dict
    business_purpose: str
    change_summary: str
    actor_type: str
    actor_id: str
    session_id: str
    request_id: str


@dataclass(frozen=True, slots=True)
class AssetFinalizationRequestResult:
    session: AssetUploadRecord
    workflow_id: str
    payload: AssetFinalizationInput
    idempotent_replay: bool


class AssetFinalizationLauncher(Protocol):
    async def start(self, workflow_id: str, payload: AssetFinalizationInput) -> None: ...


class SqlAlchemyAssetFinalizationStore:
    def __init__(self, session: AsyncSession, workspace_id: UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id

    async def request(
        self,
        upload_session_id: UUID,
        command: RequestAssetFinalizationCommand,
        context: UploadMutationContext,
    ) -> AssetFinalizationRequestResult:
        item = await self._session.scalar(
            select(AssetUploadSession).where(
                AssetUploadSession.workspace_id == self._workspace_id,
                AssetUploadSession.id == upload_session_id,
            ).with_for_update()
        )
        if item is None:
            raise AssetUploadNotFoundError("Upload session was not found")
        request_hash = _request_hash(command)
        if item.finalization_idempotency_key is not None:
            if item.finalization_idempotency_key != context.idempotency_key:
                raise AssetUploadConflictError("Finalization already uses another Idempotency-Key")
            if item.finalization_request_hash != request_hash:
                raise AssetUploadConflictError("Finalization Idempotency-Key payload does not match")
            if item.finalization_payload is None or item.finalization_workflow_id is None:
                raise AssetUploadConflictError("Finalization request is incomplete")
            return AssetFinalizationRequestResult(
                session=_upload_record(item),
                workflow_id=item.finalization_workflow_id,
                payload=AssetFinalizationInput(**item.finalization_payload),
                idempotent_replay=True,
            )
        if item.state != "ready_to_finalize" or item.scan_status != "clean":
            raise AssetUploadConflictError("Only a clean upload can be finalized")
        if not all(
            (
                item.verified_size,
                item.verified_sha256,
                item.verified_mime_type,
                item.scanned_at,
                item.scan_provider,
            )
        ):
            raise AssetUploadConflictError("Verified scan evidence is incomplete")

        asset_id = item.target_asset_id or uuid4()
        if item.target_asset_id is None:
            if command.slug is None:
                raise AssetUploadConflictError("A slug is required when creating an asset")
            collision = await self._session.scalar(
                select(BusinessObject.id).where(
                    BusinessObject.workspace_id == self._workspace_id,
                    BusinessObject.object_type == "asset",
                    BusinessObject.slug == command.slug,
                )
            )
            if collision is not None:
                raise AssetUploadConflictError("Asset slug already exists")
        else:
            target = await self._session.scalar(
                select(BusinessObject).where(
                    BusinessObject.workspace_id == self._workspace_id,
                    BusinessObject.id == item.target_asset_id,
                    BusinessObject.object_type == "asset",
                )
            )
            if target is None:
                raise AssetUploadNotFoundError("Target asset was not found")
            if command.slug is not None and command.slug != target.slug:
                raise AssetUploadConflictError("An existing asset slug cannot be changed here")

        asset_version_id = uuid4()
        blob_id = uuid4()
        destination = (
            f"workspaces/{self._workspace_id}/assets/{asset_id}/versions/"
            f"{asset_version_id}/original/{item.verified_sha256}"
        )
        workflow_id = f"grovello-asset-finalize-{self._workspace_id}-{item.id}"
        payload = AssetFinalizationInput(
            workspace_id=str(self._workspace_id),
            upload_session_id=str(item.id),
            request_hash=request_hash,
            object_key=item.staging_object_key,
            expected_provider_version_id=item.verified_provider_version_id,
            expected_content_type=item.verified_mime_type,
            expected_content_length=item.verified_size,
            expected_sha256=item.verified_sha256,
            asset_id=str(asset_id),
            asset_version_id=str(asset_version_id),
            blob_id=str(blob_id),
            destination_object_key=destination,
            name=command.name,
            slug=command.slug,
            locale=command.locale,
            status=command.status,
            metadata=command.metadata,
            business_purpose=item.business_purpose,
            change_summary=command.change_summary,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            session_id=context.session_id,
            request_id=context.request_id,
        )
        item.state = "finalizing"
        item.finalization_idempotency_key = context.idempotency_key
        item.finalization_request_hash = request_hash
        item.finalization_payload = _payload_dict(payload)
        item.finalization_workflow_id = workflow_id
        item.staging_cleanup_status = "pending"
        self._session.add(
            AuditEvent(
                id=uuid4(), workspace_id=self._workspace_id, actor_type=context.actor_type,
                actor_id=context.actor_id, session_id=context.session_id, request_id=context.request_id,
                action="asset.upload.finalization_requested", resource_type="asset_upload_session",
                resource_id=str(item.id), outcome="succeeded", reason=item.business_purpose,
                evidence={"state": "finalizing", "requestedStatus": command.status},
            )
        )
        self._session.add(
            OutboxEvent(
                id=uuid4(), workspace_id=self._workspace_id,
                aggregate_type="asset_upload_session", aggregate_id=str(item.id),
                event_type="AssetFinalizationRequested", event_version=1,
                payload={"workflowId": workflow_id, "requestedStatus": command.status},
            )
        )
        await self._session.flush()
        await self._session.refresh(item)
        return AssetFinalizationRequestResult(
            session=_upload_record(item),
            workflow_id=workflow_id,
            payload=payload,
            idempotent_replay=False,
        )

    async def commit(self) -> None:
        await self._session.commit()


def _request_hash(command: RequestAssetFinalizationCommand) -> str:
    body = json.dumps(
        {
            "name": command.name,
            "slug": command.slug,
            "locale": command.locale,
            "status": command.status,
            "metadata": command.metadata,
            "changeSummary": command.change_summary,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(body).hexdigest()


def _payload_dict(payload: AssetFinalizationInput) -> dict:
    return {field: getattr(payload, field) for field in payload.__dataclass_fields__}


def _upload_record(item: AssetUploadSession) -> AssetUploadRecord:
    from grovello.asset_uploads import SqlAlchemyAssetUploadStore

    return SqlAlchemyAssetUploadStore._record(item)
