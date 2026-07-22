import asyncio
import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import boto3
from botocore.exceptions import ClientError
from grovello.asset_downloads import AssetDownloadDeniedError, SqlAlchemyAssetDownloadStore
from grovello.asset_finalization import (
    RequestAssetFinalizationCommand,
    SqlAlchemyAssetFinalizationStore,
)
from grovello.asset_uploads import UploadMutationContext
from grovello.config import get_settings
from grovello.database import session_factory, workspace_session
from grovello.models import (
    AssetBlob,
    AssetUploadSession,
    AssetVersionFile,
    AuditEvent,
    BusinessObject,
    BusinessObjectVersion,
)
from grovello.storage_factory import build_object_storage
from sqlalchemy import func, select, text
from temporalio.client import Client

WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")
BUCKET = os.environ.get("GROVELLO_OBJECT_STORAGE_BUCKET", "grovello")


def mutation_context(case: str) -> UploadMutationContext:
    return UploadMutationContext(
        actor_type="user",
        actor_id="p2c3-integration",
        session_id="p2c3-integration",
        request_id=f"p2c3-{case}",
        idempotency_key=f"p2c3-finalize-{case}",
    )


async def prepare_clean_upload(s3, content: bytes, *, target_asset_id: UUID | None = None):
    upload_id = uuid4()
    object_key = f"workspaces/{WORKSPACE_ID}/staging/{upload_id}/{uuid4()}"
    checksum = hashlib.sha256(content).hexdigest()
    response = s3.put_object(
        Bucket=BUCKET,
        Key=object_key,
        Body=content,
        ContentType="application/pdf",
        Metadata={"sha256": checksum},
    )
    now = datetime.now(UTC)
    async with workspace_session(WORKSPACE_ID) as session:
        session.add(
            AssetUploadSession(
                id=upload_id,
                workspace_id=WORKSPACE_ID,
                target_asset_id=target_asset_id,
                actor_id="p2c3-integration",
                business_purpose="Validate governed asset finalization",
                session_id="p2c3-integration",
                request_id=f"p2c3-prepare-{upload_id}",
                idempotency_key=f"p2c3-upload-{upload_id}",
                completion_idempotency_key=f"p2c3-complete-{upload_id}",
                workflow_id=f"grovello-p2c3-verified-{upload_id}",
                state="ready_to_finalize",
                original_filename=f"p2c3-{upload_id}.pdf",
                declared_mime_type="application/pdf",
                declared_size=len(content),
                declared_sha256=checksum,
                staging_object_key=object_key,
                expires_at=now + timedelta(minutes=10),
                completed_at=now,
                verified_size=len(content),
                verified_sha256=checksum,
                verified_mime_type="application/pdf",
                verified_at=now,
                verified_provider_version_id=response.get("VersionId"),
                verified_etag=response.get("ETag", "").strip('"') or None,
                scan_status="clean",
                scan_provider="clamav",
                scan_reference=f"p2c3-clean-{upload_id}",
                scan_attempts=1,
                scanned_at=now,
            )
        )
    return upload_id, object_key, response.get("VersionId"), checksum


async def request_finalization(
    upload_id: UUID,
    *,
    case: str,
    name: str,
    slug: str | None,
    status: str,
):
    command = RequestAssetFinalizationCommand(
        name=name,
        slug=slug,
        locale="en",
        status=status,
        metadata={"fixture": "fictional", "integrationCase": case},
        change_summary=f"P2-C3 {case} integration",
    )
    async with workspace_session(WORKSPACE_ID) as session:
        result = await SqlAlchemyAssetFinalizationStore(session, WORKSPACE_ID).request(
            upload_id,
            command,
            mutation_context(f"{case}-{upload_id}"),
        )
    return result, command


async def start_workflow(client: Client, result) -> str:
    handle = await client.start_workflow(
        "grovello-asset-finalization",
        result.payload,
        id=result.workflow_id,
        task_queue=os.environ.get("GROVELLO_TEMPORAL_TASK_QUEUE", "grovello-growth"),
    )
    return await handle.result()


async def authorize_download(asset_id: UUID, version_id: UUID):
    storage = build_object_storage(get_settings())
    assert storage is not None
    async with session_factory() as session:
        await session.execute(
            text("SELECT set_config('app.workspace_id', :workspace_id, true)"),
            {"workspace_id": str(WORKSPACE_ID)},
        )
        return await SqlAlchemyAssetDownloadStore(
            session,
            WORKSPACE_ID,
            storage,
            ttl_seconds=60,
        ).authorize(asset_id, version_id, mutation_context("download"))


def assert_missing(s3, object_key: str) -> None:
    try:
        s3.head_object(Bucket=BUCKET, Key=object_key)
    except ClientError as error:
        assert error.response["ResponseMetadata"]["HTTPStatusCode"] == 404
    else:
        raise AssertionError(f"Expected object to be absent: {object_key}")


async def main() -> None:
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["GROVELLO_OBJECT_STORAGE_ENDPOINT"],
        region_name=os.environ.get("GROVELLO_OBJECT_STORAGE_REGION", "us-east-1"),
        aws_access_key_id=os.environ["GROVELLO_OBJECT_STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["GROVELLO_OBJECT_STORAGE_SECRET_ACCESS_KEY"],
    )
    client = await Client.connect(
        os.environ.get("GROVELLO_TEMPORAL_ADDRESS", "temporal:7233"),
        namespace=os.environ.get("GROVELLO_TEMPORAL_NAMESPACE", "default"),
    )
    cleanup: list[tuple[str, str | None]] = []

    first_upload, first_staging, _, _ = await prepare_clean_upload(
        s3, b"Grovello P2-C3 immutable asset version one"
    )
    first, first_command = await request_finalization(
        first_upload,
        case="create",
        name="P2-C3 Governed Asset",
        slug=f"p2c3-governed-asset-{first_upload}",
        status="active",
    )
    assert await start_workflow(client, first) == "finalized"
    assert_missing(s3, first_staging)

    replay, _ = await request_finalization(
        first_upload,
        case="create",
        name=first_command.name,
        slug=first_command.slug,
        status="active",
    )
    assert replay.idempotent_replay
    assert replay.payload == first.payload

    first_asset_id = UUID(first.payload.asset_id)
    first_version_id = UUID(first.payload.asset_version_id)
    download = await authorize_download(first_asset_id, first_version_id)
    assert download.asset_id == first_asset_id
    assert download.sha256 == first.payload.expected_sha256
    assert 0 < (download.grant.expires_at - datetime.now(UTC)).total_seconds() <= 60

    second_upload, second_staging, _, _ = await prepare_clean_upload(
        s3,
        b"Grovello P2-C3 immutable asset version two",
        target_asset_id=first_asset_id,
    )
    second, _ = await request_finalization(
        second_upload,
        case="update",
        name="P2-C3 Governed Asset Draft Update",
        slug=None,
        status="draft",
    )
    assert await start_workflow(client, second) == "finalized"
    assert_missing(s3, second_staging)
    try:
        await authorize_download(first_asset_id, UUID(second.payload.asset_version_id))
    except AssetDownloadDeniedError:
        pass
    else:
        raise AssertionError("Draft asset version unexpectedly received a download grant")

    failed_upload, failed_staging, failed_staging_version, _ = await prepare_clean_upload(
        s3, b"Grovello P2-C3 compensated promotion"
    )
    failed, _ = await request_finalization(
        failed_upload,
        case="compensation",
        name="P2-C3 Compensation Collision",
        slug=f"p2c3-compensation-{failed_upload}",
        status="active",
    )
    async with workspace_session(WORKSPACE_ID) as session:
        session.add(
            BusinessObject(
                id=uuid4(),
                workspace_id=WORKSPACE_ID,
                object_type="asset",
                slug=failed.payload.slug,
                name="Intentional integration collision",
                status="draft",
                current_version=1,
            )
        )
    assert await start_workflow(client, failed) == "failed"
    assert_missing(s3, failed.payload.destination_object_key)
    cleanup.append((failed_staging, failed_staging_version))

    async with workspace_session(WORKSPACE_ID) as session:
        first_session = await session.get(AssetUploadSession, first_upload)
        second_session = await session.get(AssetUploadSession, second_upload)
        failed_session = await session.get(AssetUploadSession, failed_upload)
        asset = await session.get(BusinessObject, first_asset_id)
        versions = await session.scalar(
            select(func.count()).select_from(BusinessObjectVersion).where(
                BusinessObjectVersion.object_id == first_asset_id
            )
        )
        bindings = await session.scalar(
            select(func.count()).select_from(AssetVersionFile).where(
                AssetVersionFile.business_object_version_id.in_(
                    [UUID(first.payload.asset_version_id), UUID(second.payload.asset_version_id)]
                )
            )
        )
        blobs = (
            await session.scalars(
                select(AssetBlob).where(
                    AssetBlob.id.in_([UUID(first.payload.blob_id), UUID(second.payload.blob_id)])
                )
            )
        ).all()
        audits = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.action.in_(
                    {
                        "asset.upload.finalized",
                        "asset.upload.finalization_failed",
                        "asset.download.request_authorized",
                    }
                )
            )
        )
        assert first_session is not None and first_session.staging_cleanup_status == "complete"
        assert second_session is not None and second_session.staging_cleanup_status == "complete"
        assert (
            failed_session is not None
            and failed_session.failure_code == "asset_finalization_commit_failed"
        )
        assert asset is not None and asset.current_version == 2 and asset.status == "draft"
        assert versions == 2
        assert bindings == 2
        assert len(blobs) == 2 and all(blob.scan_status == "clean" for blob in blobs)
        assert audits >= 4
        cleanup.extend((blob.object_key, blob.provider_version_id) for blob in blobs)

    for object_key, provider_version_id in cleanup:
        request = {"Bucket": BUCKET, "Key": object_key}
        if provider_version_id:
            request["VersionId"] = provider_version_id
        s3.delete_object(**request)
    print(
        "create=finalized;replay=idempotent;update=version-2;download=active-only;"
        "compensation=failed-closed;staging_cleanup=complete"
    )


if __name__ == "__main__":
    asyncio.run(main())
