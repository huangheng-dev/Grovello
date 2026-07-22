import runpy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from grovello.access import OWNER_PERMISSIONS, access_directory
from grovello.models import Base
from grovello.object_storage import (
    AbortMultipartUploadRequest,
    CopyObjectRequest,
    CreateDownloadGrantRequest,
    CreateUploadGrantRequest,
    DeleteObjectRequest,
    DownloadGrant,
    ObjectStorage,
    ObjectStorageHealth,
    StorageObjectRef,
    StoredObject,
    UploadGrant,
    UploadGrantMethod,
)

WORKSPACE_ID = UUID("00000000-0000-4000-8000-000000000001")
SHA256 = "a" * 64


class FakeObjectStorage:
    async def health(self) -> ObjectStorageHealth:
        return ObjectStorageHealth(available=True, provider="test")

    async def create_upload_grant(self, request: CreateUploadGrantRequest) -> UploadGrant:
        return UploadGrant(
            method=UploadGrantMethod.POST,
            url="https://storage.example.invalid/upload",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
            fields={"key": request.destination.object_key},
        )

    async def head_object(self, location: StorageObjectRef) -> StoredObject:
        return StoredObject(location, 128, "image/png", SHA256)

    async def calculate_sha256(self, location: StorageObjectRef) -> str:
        return SHA256

    async def iter_object_chunks(self, location: StorageObjectRef, *, chunk_size: int = 1024 * 1024):
        yield b"asset"

    async def copy_object(self, request: CopyObjectRequest) -> StoredObject:
        return StoredObject(request.destination, 128, "image/png", request.expected_sha256)

    async def create_download_grant(self, request: CreateDownloadGrantRequest) -> DownloadGrant:
        return DownloadGrant(
            url=f"https://storage.example.invalid/{request.source.object_key}",
            expires_at=datetime.now(UTC) + timedelta(seconds=request.expires_in_seconds),
        )

    async def delete_object(self, request: DeleteObjectRequest) -> None:
        return None

    async def abort_multipart_upload(self, request: AbortMultipartUploadRequest) -> None:
        return None


def test_asset_tables_are_part_of_the_canonical_metadata() -> None:
    assert {
        "asset_upload_sessions",
        "asset_blobs",
        "asset_version_files",
    } <= set(Base.metadata.tables)

    binding = Base.metadata.tables["asset_version_files"]
    foreign_key_targets = {
        tuple(sorted(element.target_fullname for element in constraint.elements))
        for constraint in binding.foreign_key_constraints
    }
    assert ("business_object_versions.id", "business_object_versions.workspace_id") in foreign_key_targets
    assert ("asset_blobs.id", "asset_blobs.workspace_id") in foreign_key_targets


def test_asset_migration_enables_rls_for_every_asset_table() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0004_asset_storage_foundation.py"
    )
    migration = runpy.run_path(str(migration_path))
    assert migration["down_revision"] == "0003"
    assert migration["TENANT_TABLES"] == (
        "asset_upload_sessions",
        "asset_blobs",
        "asset_version_files",
    )

    source = migration_path.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "current_setting('app.workspace_id'" in source


def test_asset_finalization_migration_is_reversible_and_fail_closed() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0007_asset_finalization.py"
    )
    migration = runpy.run_path(str(migration_path))
    assert migration["down_revision"] == "0006"
    source = migration_path.read_text(encoding="utf-8")
    assert "'finalizing'" in source
    assert "finalization_request_hash" in source
    assert "staging_cleanup_status" in source
    assert "fk_asset_upload_sessions_finalized_blob" in source


def test_asset_permissions_follow_risk_tiers_and_seed_roles() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "migrations"
        / "versions"
        / "0004_asset_storage_foundation.py"
    )
    permissions = dict(
        (key, risk_tier)
        for key, _description, risk_tier in runpy.run_path(str(migration_path))["ASSET_PERMISSIONS"]
    )
    assert permissions == {
        "asset.read": "R0",
        "asset.download": "R1",
        "asset.write": "R1",
        "asset.approve": "R2",
        "asset.archive": "R2",
        "asset.purge": "R4",
    }
    assert set(permissions) <= OWNER_PERMISSIONS

    analyst = access_directory._grants[("northstar-analyst", WORKSPACE_ID)]
    assert {"asset.read", "asset.download"} <= analyst.permissions
    assert "asset.write" not in analyst.permissions


def test_storage_contract_is_provider_neutral_and_tenant_scoped() -> None:
    storage = FakeObjectStorage()
    assert isinstance(storage, ObjectStorage)

    source = StorageObjectRef(WORKSPACE_ID, "workspaces/source/staging/file")
    destination = StorageObjectRef(WORKSPACE_ID, "workspaces/source/assets/file")
    request = CopyObjectRequest(source, destination, SHA256)
    assert request.source.workspace_id == request.destination.workspace_id


def test_storage_contract_rejects_unsafe_keys_and_cross_tenant_copy() -> None:
    with pytest.raises(ValueError, match="normalized relative key"):
        StorageObjectRef(WORKSPACE_ID, "../other-workspace/file")

    other_workspace = UUID("00000000-0000-4000-8000-000000000002")
    source = StorageObjectRef(WORKSPACE_ID, "workspaces/one/staging/file")
    destination = StorageObjectRef(other_workspace, "workspaces/two/assets/file")
    with pytest.raises(ValueError, match="cannot cross workspace"):
        CopyObjectRequest(source, destination, SHA256)


def test_upload_grant_request_requires_integrity_and_bounded_expiry() -> None:
    destination = StorageObjectRef(WORKSPACE_ID, "workspaces/source/staging/file")
    with pytest.raises(ValueError, match="lowercase hexadecimal"):
        CreateUploadGrantRequest(destination, "image/png", 128, "not-a-checksum", 1800)
    with pytest.raises(ValueError, match="between 1 and 3600"):
        CreateUploadGrantRequest(destination, "image/png", 128, SHA256, 7200)
    with pytest.raises(ValueError, match="between 1 and 3600"):
        CreateDownloadGrantRequest(destination, 7200)
