from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from grovello.models import AssetUploadSession, AuditEvent, BusinessObject, OutboxEvent
from grovello.object_storage import CreateUploadGrantRequest, ObjectStorage, StorageObjectRef, UploadGrant

AssetUploadState = Literal[
    "initiated",
    "uploaded",
    "verifying",
    "scanning",
    "ready_to_finalize",
    "finalizing",
    "finalized",
    "quarantined",
    "failed",
    "expired",
    "cancelled",
]

SUPPORTED_UPLOAD_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "application/pdf"})


class AssetUploadError(RuntimeError):
    pass


class AssetUploadNotFoundError(AssetUploadError):
    pass


class AssetUploadConflictError(AssetUploadError):
    pass


class AssetUploadExpiredError(AssetUploadConflictError):
    pass


class AssetUploadUnavailableError(AssetUploadError):
    pass


@dataclass(frozen=True, slots=True)
class UploadMutationContext:
    actor_type: str
    actor_id: str
    session_id: str
    request_id: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CreateUploadCommand:
    original_filename: str
    content_type: str
    content_length: int
    checksum_sha256: str
    business_purpose: str
    target_asset_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AssetUploadRecord:
    id: UUID
    workspace_id: UUID
    target_asset_id: UUID | None
    actor_id: str
    business_purpose: str
    state: str
    original_filename: str
    declared_mime_type: str
    declared_size: int
    declared_sha256: str
    expires_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    workflow_id: str | None
    failure_code: str | None
    failure_detail: str | None
    verified_size: int | None
    verified_sha256: str | None
    verified_mime_type: str | None
    verified_at: datetime | None
    scan_status: str
    scan_provider: str | None
    scan_reference: str | None
    scan_attempts: int
    scanned_at: datetime | None
    quarantine_object_key: str | None
    quarantined_at: datetime | None
    finalization_workflow_id: str | None
    finalized_blob_id: UUID | None
    finalized_asset_id: UUID | None
    finalized_asset_version_id: UUID | None
    finalized_at: datetime | None
    staging_cleanup_status: str
    staging_cleanup_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CreateUploadResult:
    session: AssetUploadRecord
    grant: UploadGrant
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class UploadMutationResult:
    session: AssetUploadRecord
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class AssetVerificationInput:
    workspace_id: str
    upload_session_id: str
    object_key: str
    expected_content_type: str
    expected_content_length: int
    expected_sha256: str


class AssetVerificationLauncher(Protocol):
    async def start(self, workflow_id: str, payload: AssetVerificationInput) -> None: ...

    async def cancel(self, workflow_id: str) -> None: ...


class AssetUploadStore(Protocol):
    source: Literal["live"]

    async def create(
        self, command: CreateUploadCommand, context: UploadMutationContext
    ) -> CreateUploadResult: ...

    async def get(self, upload_session_id: UUID) -> AssetUploadRecord: ...

    async def complete(
        self, upload_session_id: UUID, context: UploadMutationContext
    ) -> tuple[UploadMutationResult, AssetVerificationInput]: ...

    async def cancel(
        self, upload_session_id: UUID, context: UploadMutationContext
    ) -> UploadMutationResult: ...

    async def commit(self) -> None: ...


class SqlAlchemyAssetUploadStore:
    source: Literal["live"] = "live"

    def __init__(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        storage: ObjectStorage,
        *,
        max_upload_bytes: int,
        upload_ttl_seconds: int,
    ) -> None:
        self._session = session
        self._workspace_id = workspace_id
        self._storage = storage
        self._max_upload_bytes = max_upload_bytes
        self._upload_ttl_seconds = upload_ttl_seconds

    async def create(
        self, command: CreateUploadCommand, context: UploadMutationContext
    ) -> CreateUploadResult:
        existing = await self._by_create_key(context.idempotency_key)
        if existing is not None:
            self._assert_same_create(existing, command)
            return CreateUploadResult(
                session=self._record(existing),
                grant=await self._grant(existing),
                idempotent_replay=True,
            )
        self._validate(command)
        if command.target_asset_id is not None:
            target = await self._session.scalar(
                select(BusinessObject).where(
                    BusinessObject.workspace_id == self._workspace_id,
                    BusinessObject.id == command.target_asset_id,
                    BusinessObject.object_type == "asset",
                )
            )
            if target is None:
                raise AssetUploadNotFoundError("Target asset was not found")
        upload_id = uuid4()
        now = datetime.now(UTC)
        item = AssetUploadSession(
            id=upload_id,
            workspace_id=self._workspace_id,
            target_asset_id=command.target_asset_id,
            actor_id=context.actor_id,
            business_purpose=command.business_purpose,
            session_id=context.session_id,
            request_id=context.request_id,
            idempotency_key=context.idempotency_key,
            state="initiated",
            original_filename=command.original_filename,
            declared_mime_type=command.content_type,
            declared_size=command.content_length,
            declared_sha256=command.checksum_sha256,
            staging_object_key=f"workspaces/{self._workspace_id}/staging/{upload_id}/{uuid4()}",
            expires_at=now + timedelta(seconds=self._upload_ttl_seconds),
        )
        self._session.add(item)
        self._append_events(item, context, "asset.upload.initiated", "AssetUploadInitiated")
        await self._session.flush()
        return CreateUploadResult(
            session=self._record(item),
            grant=await self._grant(item),
            idempotent_replay=False,
        )

    async def get(self, upload_session_id: UUID) -> AssetUploadRecord:
        return self._record(await self._require(upload_session_id))

    async def complete(
        self, upload_session_id: UUID, context: UploadMutationContext
    ) -> tuple[UploadMutationResult, AssetVerificationInput]:
        item = await self._require(upload_session_id, lock=True)
        if item.state == "initiated":
            if item.expires_at <= datetime.now(UTC):
                item.state = "expired"
                item.failure_code = "upload_session_expired"
                self._append_events(item, context, "asset.upload.expired", "AssetUploadExpired")
                await self._session.commit()
                raise AssetUploadExpiredError("Upload session has expired")
            item.state = "uploaded"
            item.completed_at = datetime.now(UTC)
            item.completion_idempotency_key = context.idempotency_key
            item.workflow_id = f"grovello-asset-verify-{self._workspace_id}-{item.id}"
            self._append_events(
                item, context, "asset.upload.completed", "AssetUploadVerificationRequested"
            )
            replay = False
        elif item.state in {"uploaded", "verifying", "scanning", "ready_to_finalize", "quarantined"}:
            if item.completion_idempotency_key != context.idempotency_key:
                raise AssetUploadConflictError("Completion Idempotency-Key does not match")
            replay = True
        else:
            raise AssetUploadConflictError(f"Upload session cannot be completed from {item.state}")
        await self._session.flush()
        await self._session.refresh(item)
        return UploadMutationResult(self._record(item), replay), self._verification_input(item)

    async def cancel(
        self, upload_session_id: UUID, context: UploadMutationContext
    ) -> UploadMutationResult:
        item = await self._require(upload_session_id, lock=True)
        if item.state == "cancelled":
            return UploadMutationResult(self._record(item), True)
        if item.state in {
            "ready_to_finalize",
            "finalizing",
            "finalized",
            "failed",
            "expired",
            "quarantined",
        }:
            raise AssetUploadConflictError(f"Upload session cannot be cancelled from {item.state}")
        item.state = "cancelled"
        item.cancelled_at = datetime.now(UTC)
        self._append_events(item, context, "asset.upload.cancelled", "AssetUploadCancelled")
        await self._session.flush()
        await self._session.refresh(item)
        return UploadMutationResult(self._record(item), False)

    async def commit(self) -> None:
        await self._session.commit()

    async def _require(self, upload_session_id: UUID, *, lock: bool = False) -> AssetUploadSession:
        statement = select(AssetUploadSession).where(
            AssetUploadSession.workspace_id == self._workspace_id,
            AssetUploadSession.id == upload_session_id,
        )
        if lock:
            statement = statement.with_for_update()
        item = await self._session.scalar(statement)
        if item is None:
            raise AssetUploadNotFoundError("Upload session was not found")
        return item

    async def _by_create_key(self, key: str) -> AssetUploadSession | None:
        return await self._session.scalar(
            select(AssetUploadSession).where(
                AssetUploadSession.workspace_id == self._workspace_id,
                AssetUploadSession.idempotency_key == key,
            )
        )

    def _validate(self, command: CreateUploadCommand) -> None:
        if command.content_type not in SUPPORTED_UPLOAD_TYPES:
            raise AssetUploadConflictError("Unsupported asset content type")
        if command.content_length <= 0 or command.content_length > self._max_upload_bytes:
            raise AssetUploadConflictError("Asset content length exceeds the configured limit")

    def _assert_same_create(self, item: AssetUploadSession, command: CreateUploadCommand) -> None:
        values = (
            item.original_filename == command.original_filename,
            item.declared_mime_type == command.content_type,
            item.declared_size == command.content_length,
            item.declared_sha256 == command.checksum_sha256,
            item.business_purpose == command.business_purpose,
            item.target_asset_id == command.target_asset_id,
        )
        if not all(values):
            raise AssetUploadConflictError("Idempotency-Key was already used with another request")

    async def _grant(self, item: AssetUploadSession) -> UploadGrant:
        if item.state != "initiated" or item.expires_at <= datetime.now(UTC):
            raise AssetUploadConflictError("Upload session no longer accepts uploads")
        remaining = max(
            1,
            min(
                self._upload_ttl_seconds,
                int((item.expires_at - datetime.now(UTC)).total_seconds()),
            ),
        )
        return await self._storage.create_upload_grant(
            CreateUploadGrantRequest(
                destination=StorageObjectRef(self._workspace_id, item.staging_object_key),
                content_type=item.declared_mime_type,
                content_length=item.declared_size,
                checksum_sha256=item.declared_sha256,
                expires_in_seconds=remaining,
            )
        )

    def _append_events(
        self,
        item: AssetUploadSession,
        context: UploadMutationContext,
        action: str,
        event_type: str,
    ) -> None:
        self._session.add(
            AuditEvent(
                id=uuid4(), workspace_id=self._workspace_id, actor_type=context.actor_type,
                actor_id=context.actor_id, session_id=context.session_id, request_id=context.request_id,
                action=action, resource_type="asset_upload_session", resource_id=str(item.id),
                outcome="succeeded", evidence={"state": item.state, "businessPurpose": item.business_purpose},
            )
        )
        self._session.add(
            OutboxEvent(
                id=uuid4(), workspace_id=self._workspace_id, aggregate_type="asset_upload_session",
                aggregate_id=str(item.id), event_type=event_type, event_version=1,
                payload={"state": item.state, "workflowId": item.workflow_id},
            )
        )

    def _verification_input(self, item: AssetUploadSession) -> AssetVerificationInput:
        return AssetVerificationInput(
            workspace_id=str(self._workspace_id), upload_session_id=str(item.id),
            object_key=item.staging_object_key, expected_content_type=item.declared_mime_type,
            expected_content_length=item.declared_size, expected_sha256=item.declared_sha256,
        )

    @staticmethod
    def _record(item: AssetUploadSession) -> AssetUploadRecord:
        return AssetUploadRecord(
            id=item.id, workspace_id=item.workspace_id, target_asset_id=item.target_asset_id,
            actor_id=item.actor_id, business_purpose=item.business_purpose, state=item.state,
            original_filename=item.original_filename, declared_mime_type=item.declared_mime_type,
            declared_size=item.declared_size, declared_sha256=item.declared_sha256,
            expires_at=item.expires_at, completed_at=item.completed_at, cancelled_at=item.cancelled_at,
            workflow_id=item.workflow_id, failure_code=item.failure_code, failure_detail=item.failure_detail,
            verified_size=item.verified_size, verified_sha256=item.verified_sha256,
            verified_mime_type=item.verified_mime_type, verified_at=item.verified_at,
            scan_status=item.scan_status, scan_provider=item.scan_provider,
            scan_reference=item.scan_reference, scan_attempts=item.scan_attempts,
            scanned_at=item.scanned_at, quarantine_object_key=item.quarantine_object_key,
            quarantined_at=item.quarantined_at,
            finalization_workflow_id=item.finalization_workflow_id,
            finalized_blob_id=item.finalized_blob_id,
            finalized_asset_id=item.finalized_asset_id,
            finalized_asset_version_id=item.finalized_asset_version_id,
            finalized_at=item.finalized_at,
            staging_cleanup_status=item.staging_cleanup_status,
            staging_cleanup_at=item.staging_cleanup_at,
            created_at=item.created_at, updated_at=item.updated_at,
        )
