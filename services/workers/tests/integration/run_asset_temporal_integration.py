import asyncio
import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import boto3
from botocore.exceptions import ClientError
from grovello.asset_uploads import AssetVerificationInput
from grovello.database import workspace_session
from grovello.models import AssetBlob, AssetUploadSession, AuditEvent
from sqlalchemy import func, select
from temporalio.client import Client


async def run_case(s3, workspace_id: UUID, content: bytes, expected_state: str) -> tuple[str, str]:
    workspace_id = UUID("00000000-0000-4000-8000-000000000001")
    upload_id = uuid4()
    workflow_id = f"grovello-asset-verify-{workspace_id}-{upload_id}"
    object_key = f"workspaces/{workspace_id}/staging/{upload_id}/{uuid4()}"
    checksum = hashlib.sha256(content).hexdigest()
    response = s3.put_object(
        Bucket=os.environ.get("GROVELLO_OBJECT_STORAGE_BUCKET", "grovello"),
        Key=object_key,
        Body=content,
        ContentType="application/pdf",
        Metadata={"sha256": checksum},
    )
    async with workspace_session(workspace_id) as session:
        session.add(
            AssetUploadSession(
                id=upload_id,
                workspace_id=workspace_id,
                actor_id="p2c2-integration",
                business_purpose="Verify durable malware scanning and quarantine",
                session_id="p2c2-integration",
                request_id="p2c2-integration",
                idempotency_key=f"create-{upload_id}",
                completion_idempotency_key=f"complete-{upload_id}",
                workflow_id=workflow_id,
                state="uploaded",
                original_filename="p2c2-scanning.pdf",
                declared_mime_type="application/pdf",
                declared_size=len(content),
                declared_sha256=checksum,
                staging_object_key=object_key,
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
                completed_at=datetime.now(UTC),
            )
        )

    client = await Client.connect(
        os.environ.get("GROVELLO_TEMPORAL_ADDRESS", "temporal:7233"),
        namespace=os.environ.get("GROVELLO_TEMPORAL_NAMESPACE", "default"),
    )
    handle = await client.start_workflow(
        "grovello-asset-upload-verification",
        AssetVerificationInput(
            workspace_id=str(workspace_id),
            upload_session_id=str(upload_id),
            object_key=object_key,
            expected_content_type="application/pdf",
            expected_content_length=len(content),
            expected_sha256=checksum,
        ),
        id=workflow_id,
        task_queue=os.environ.get("GROVELLO_TEMPORAL_TASK_QUEUE", "grovello-growth"),
    )
    result = await handle.result()
    async with workspace_session(workspace_id) as session:
        item = await session.scalar(select(AssetUploadSession).where(AssetUploadSession.id == upload_id))
        blob_count = await session.scalar(select(func.count()).select_from(AssetBlob))
        assert item is not None
        audit_count = await session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.resource_id == str(upload_id),
                AuditEvent.action.in_(
                    {"asset.upload.scan_clean", "asset.upload.quarantined", "asset.upload.scan_failed"}
                ),
            )
        )
        assert item.state == expected_state
        assert item.verified_sha256 == checksum
        assert blob_count == 0
        assert audit_count == 1
        if expected_state == "ready_to_finalize":
            assert item.scan_status == "clean"
            cleanup_key = object_key
            cleanup_version = response.get("VersionId")
        elif expected_state == "quarantined":
            assert item.scan_status == "infected"
            assert item.quarantine_object_key is not None
            cleanup_key = item.quarantine_object_key
            cleanup_version = item.quarantine_provider_version_id
            try:
                s3.head_object(
                    Bucket=os.environ.get("GROVELLO_OBJECT_STORAGE_BUCKET", "grovello"),
                    Key=object_key,
                )
            except ClientError as error:
                assert error.response["ResponseMetadata"]["HTTPStatusCode"] == 404
            else:
                raise AssertionError("Infected staging object was not removed")
        else:
            assert item.scan_status == "failed"
            assert item.failure_code == "scanner_unavailable_after_retries"
            assert item.scan_attempts == 3
            cleanup_key = object_key
            cleanup_version = response.get("VersionId")
    delete = {
        "Bucket": os.environ.get("GROVELLO_OBJECT_STORAGE_BUCKET", "grovello"),
        "Key": cleanup_key,
    }
    if cleanup_version:
        delete["VersionId"] = cleanup_version
    s3.delete_object(**delete)
    return result, item.scan_status


async def main() -> None:
    workspace_id = UUID("00000000-0000-4000-8000-000000000001")
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["GROVELLO_OBJECT_STORAGE_ENDPOINT"],
        region_name=os.environ.get("GROVELLO_OBJECT_STORAGE_REGION", "us-east-1"),
        aws_access_key_id=os.environ["GROVELLO_OBJECT_STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["GROVELLO_OBJECT_STORAGE_SECRET_ACCESS_KEY"],
    )
    if os.environ.get("GROVELLO_P2C2_EXPECT_SCAN_FAILURE") == "true":
        failed = await run_case(
            s3,
            workspace_id,
            b"Grovello P2-C2 scanner failure and retry integration",
            "failed",
        )
        print(f"failed={failed[0]}/{failed[1]};scan_attempts=3;asset_blobs=0")
        return
    clean = await run_case(
        s3,
        workspace_id,
        b"Grovello P2-C2 clean Temporal scanning integration",
        "ready_to_finalize",
    )
    eicar = (
        b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    )
    infected = await run_case(s3, workspace_id, eicar, "quarantined")
    print(
        f"clean={clean[0]}/{clean[1]};infected={infected[0]}/{infected[1]};"
        "asset_blobs=0"
    )


if __name__ == "__main__":
    asyncio.run(main())
