from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from grovello.access import NORTHSTAR_WORKSPACE_ID
from grovello.api.dependencies import (
    get_business_import_store,
    get_import_source_verification_launcher,
    get_import_validation_launcher,
    get_workspace_onboarding_store,
)
from grovello.business_imports import (
    CreateImportJobResult,
    CreateImportMappingResult,
    ImportJobMutationResult,
    ImportJobRecord,
    ImportMappingRecord,
    ImportSourceRecord,
    ImportSourceVerificationInput,
    ImportValidationInput,
    ImportValidationReportRecord,
    ImportValidationStartResult,
)
from grovello.main import app
from grovello.object_storage import UploadGrant, UploadGrantMethod
from grovello.workspace_onboarding import (
    WorkspaceOnboardingMutationResult,
    WorkspaceOnboardingRecord,
)

JOB_ID = UUID("11111111-1111-4111-8111-111111111111")
SOURCE_ID = UUID("22222222-2222-4222-8222-222222222222")
ONBOARDING_ID = UUID("33333333-3333-4333-8333-333333333333")
SHA256 = "a" * 64


def headers(subject: str, key: str | None = None, workspace_id: UUID = NORTHSTAR_WORKSPACE_ID):
    result = {
        "X-Grovello-Dev-Subject": subject,
        "X-Grovello-Dev-Session": f"session-{subject}",
        "X-Request-ID": f"request-{subject}",
        "X-Workspace-ID": str(workspace_id),
    }
    if key:
        result["Idempotency-Key"] = key
    return result


def import_record(status: str = "uploading", workflow_id: str | None = None) -> ImportJobRecord:
    now = datetime.now(UTC)
    source_is_clean = status in {"ready_for_mapping", "mapping", "validating", "ready_for_review"}
    return ImportJobRecord(
        id=JOB_ID,
        workspace_id=NORTHSTAR_WORKSPACE_ID,
        actor_id="northstar-owner",
        business_purpose="Import the approved product catalog",
        object_type="product",
        source_format="csv",
        schema_version=1,
        locale="en",
        status=status,
        total_rows=0,
        valid_rows=0,
        invalid_rows=0,
        applied_rows=0,
        workflow_id=workflow_id,
        input_versions={},
        result_summary={},
        failure_code=None,
        failure_detail=None,
        retention_deadline=now + timedelta(days=30),
        cancelled_at=now if status == "cancelled" else None,
        completed_at=None,
        created_at=now,
        updated_at=now,
        source=ImportSourceRecord(
            id=SOURCE_ID,
            state="cancelled" if status == "cancelled" else "clean" if source_is_clean else status,
            original_filename="products.csv",
            declared_mime_type="text/csv",
            declared_size=128,
            declared_sha256=SHA256,
            verified_size=None,
            verified_mime_type=None,
            verified_sha256=None,
            verified_at=None,
            scan_status="clean" if source_is_clean else "not_started",
            scan_provider=None,
            scan_reference=None,
            scan_attempts=0,
            scanned_at=None,
            quarantined_at=None,
            expires_at=now + timedelta(minutes=30),
            deletion_deadline=now + timedelta(days=30),
            deleted_at=None,
        ),
    )


class FakeImportStore:
    source = "live"

    def __init__(self) -> None:
        self.item = import_record()
        self.create_key: str | None = None

    async def create(self, command, context):
        replay = self.create_key == context.idempotency_key
        self.create_key = context.idempotency_key
        return CreateImportJobResult(
            self.item,
            UploadGrant(
                UploadGrantMethod.POST,
                "http://localhost:9000/grovello",
                datetime.now(UTC) + timedelta(minutes=30),
                fields={
                    "key": f"workspaces/{NORTHSTAR_WORKSPACE_ID}/imports/{JOB_ID}/sources/{SOURCE_ID}",
                    "Content-Type": command.content_type,
                    "x-amz-meta-sha256": command.checksum_sha256,
                    "policy": "signed-policy",
                },
            ),
            replay,
        )

    async def list(self, limit):
        return (self.item,)

    async def get(self, job_id):
        return self.item

    async def complete(self, job_id, context):
        workflow_id = f"grovello-import-source-verify-{NORTHSTAR_WORKSPACE_ID}-{JOB_ID}"
        self.item = import_record("uploaded", workflow_id)
        return ImportJobMutationResult(self.item, False), ImportSourceVerificationInput(
            workspace_id=str(NORTHSTAR_WORKSPACE_ID),
            job_id=str(JOB_ID),
            source_id=str(SOURCE_ID),
            object_key=f"workspaces/{NORTHSTAR_WORKSPACE_ID}/imports/{JOB_ID}/sources/{SOURCE_ID}",
            expected_content_type="text/csv",
            expected_content_length=128,
            expected_sha256=SHA256,
        )

    async def cancel(self, job_id, context):
        previous = self.item
        cancelled = import_record("cancelled", previous.workflow_id)
        self.item = ImportJobRecord(
            **{
                **{field: getattr(cancelled, field) for field in cancelled.__dataclass_fields__},
                "selected_mapping_version_id": previous.selected_mapping_version_id,
                "validation_workflow_id": previous.validation_workflow_id,
            }
        )
        return ImportJobMutationResult(self.item, False)

    async def create_mapping(self, job_id, command, context):
        now = datetime.now(UTC)
        mapping = ImportMappingRecord(
            id=UUID("44444444-4444-4444-8444-444444444444"),
            job_id=JOB_ID,
            version=1,
            schema_fingerprint="b" * 64,
            business_purpose=command.business_purpose,
            source_fields=command.source_fields,
            delimiter=command.delimiter,
            fields=command.fields,
            created_by="northstar-owner",
            created_at=now,
        )
        self.item = import_record("ready_for_mapping")
        self.item = ImportJobRecord(
            **{
                **{field: getattr(self.item, field) for field in self.item.__dataclass_fields__},
                "selected_mapping_version_id": mapping.id,
            }
        )
        return CreateImportMappingResult(mapping, False)

    async def start_validation(self, job_id, command, context):
        mapping_id = self.item.selected_mapping_version_id
        assert mapping_id is not None
        self.item = ImportJobRecord(
            **{
                **{field: getattr(self.item, field) for field in self.item.__dataclass_fields__},
                "status": "validating",
                "validation_workflow_id": f"grovello-import-validate-{JOB_ID}",
            }
        )
        return ImportValidationStartResult(
            job=self.item,
            payload=ImportValidationInput(
                workspace_id=str(NORTHSTAR_WORKSPACE_ID),
                job_id=str(JOB_ID),
                mapping_version_id=str(mapping_id),
            ),
            idempotent_replay=False,
        )

    async def validation_report(self, job_id, preview_limit, issue_limit):
        return ImportValidationReportRecord(self.item, None, (), ())

    async def commit(self):
        return None


class FakeLauncher:
    def __init__(self) -> None:
        self.started = []
        self.cancelled = []

    async def start(self, workflow_id, payload):
        self.started.append((workflow_id, payload))

    async def cancel(self, workflow_id):
        self.cancelled.append(workflow_id)


class FakeValidationLauncher(FakeLauncher):
    pass


class FakeOnboardingStore:
    source = "live"

    def __init__(self) -> None:
        self.item: WorkspaceOnboardingRecord | None = None
        self.key: str | None = None

    async def create(self, command, context):
        now = datetime.now(UTC)
        replay = self.key == context.idempotency_key
        self.key = context.idempotency_key
        self.item = WorkspaceOnboardingRecord(
            id=ONBOARDING_ID,
            workspace_id=NORTHSTAR_WORKSPACE_ID,
            status="draft",
            business_purpose=command.business_purpose,
            required_object_types=command.required_object_types,
            validation_gaps=(),
            input_versions=command.input_versions,
            last_completed_step=None,
            policy_version=None,
            activation_version=0,
            activated_by=None,
            activated_at=None,
            created_at=now,
            updated_at=now,
        )
        return WorkspaceOnboardingMutationResult(self.item, replay)

    async def get(self):
        assert self.item is not None
        return self.item

    async def activate(self, command, context):
        assert self.item is not None
        self.item = WorkspaceOnboardingRecord(
            **{
                **{field: getattr(self.item, field) for field in self.item.__dataclass_fields__},
                "status": "active",
                "policy_version": command.policy_version,
                "activation_version": self.item.activation_version + 1,
                "activated_by": context.actor_id,
                "activated_at": datetime.now(UTC),
                "activation_business_purpose": command.business_purpose,
                "activation_snapshot": {
                    "objectVersions": [],
                    "policyVersion": command.policy_version,
                },
            }
        )
        return WorkspaceOnboardingMutationResult(self.item, False)


@pytest.fixture
def p2d_client() -> Iterator[
    tuple[TestClient, FakeImportStore, FakeLauncher, FakeValidationLauncher, FakeOnboardingStore]
]:
    import_store = FakeImportStore()
    launcher = FakeLauncher()
    validation_launcher = FakeValidationLauncher()
    onboarding_store = FakeOnboardingStore()
    app.dependency_overrides[get_business_import_store] = lambda: import_store
    app.dependency_overrides[get_import_source_verification_launcher] = lambda: launcher
    app.dependency_overrides[get_import_validation_launcher] = lambda: validation_launcher
    app.dependency_overrides[get_workspace_onboarding_store] = lambda: onboarding_store
    try:
        with TestClient(app) as client:
            yield client, import_store, launcher, validation_launcher, onboarding_store
    finally:
        app.dependency_overrides.pop(get_business_import_store, None)
        app.dependency_overrides.pop(get_import_source_verification_launcher, None)
        app.dependency_overrides.pop(get_import_validation_launcher, None)
        app.dependency_overrides.pop(get_workspace_onboarding_store, None)


def payload() -> dict:
    return {
        "objectType": "product",
        "sourceFormat": "csv",
        "schemaVersion": 1,
        "locale": "en",
        "originalFilename": "products.csv",
        "contentType": "text/csv",
        "contentLength": 128,
        "checksumSha256": SHA256,
        "businessPurpose": "Import the approved product catalog",
        "inputVersions": {},
    }


def test_create_import_returns_constrained_upload_without_storage_identifiers(p2d_client) -> None:
    client, _store, _launcher, _validation_launcher, _onboarding = p2d_client
    response = client.post(
        "/api/v1/import-jobs",
        headers=headers("northstar-owner", "create-products"),
        json=payload(),
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["job"]["status"] == "uploading"
    assert data["upload"]["method"] == "POST"
    assert data["upload"]["fields"]["Content-Type"] == "text/csv"
    assert data["upload"]["fields"]["x-amz-meta-sha256"] == SHA256
    assert "objectKey" not in data["job"]["source"]
    assert "providerVersionId" not in data["job"]["source"]


def test_create_import_is_idempotent_and_missing_key_is_rejected(p2d_client) -> None:
    client, _store, _launcher, _validation_launcher, _onboarding = p2d_client
    first = client.post(
        "/api/v1/import-jobs",
        headers=headers("northstar-owner", "same-import"),
        json=payload(),
    )
    replay = client.post(
        "/api/v1/import-jobs",
        headers=headers("northstar-owner", "same-import"),
        json=payload(),
    )
    missing = client.post("/api/v1/import-jobs", headers=headers("northstar-owner"), json=payload())
    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["data"]["idempotentReplay"] is True
    assert missing.status_code == 400


def test_complete_launches_temporal_without_parsing_or_applying_rows(p2d_client) -> None:
    client, store, launcher, _validation_launcher, _onboarding = p2d_client
    response = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/complete",
        headers=headers("northstar-owner", "complete-products"),
    )
    assert response.status_code == 202
    assert response.json()["data"]["job"]["status"] == "uploaded"
    assert response.json()["data"]["job"]["appliedRows"] == 0
    assert len(launcher.started) == 1
    assert store.item.workflow_id is not None


def test_read_only_actor_can_read_but_cannot_create_or_cancel(p2d_client) -> None:
    client, _store, _launcher, _validation_launcher, _onboarding = p2d_client
    listed = client.get("/api/v1/import-jobs", headers=headers("northstar-analyst"))
    created = client.post(
        "/api/v1/import-jobs",
        headers=headers("northstar-analyst", "denied-create"),
        json=payload(),
    )
    cancelled = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/cancel",
        headers=headers("northstar-analyst", "denied-cancel"),
    )
    assert listed.status_code == 200
    assert created.status_code == 403
    assert cancelled.status_code == 403


def test_workspace_onboarding_creation_is_separate_from_activation(p2d_client) -> None:
    client, _store, _launcher, _validation_launcher, _onboarding = p2d_client
    response = client.post(
        "/api/v1/workspace-onboarding",
        headers=headers("northstar-owner", "start-business-setup"),
        json={
            "businessPurpose": "Configure governed business truth",
            "requiredObjectTypes": ["brand", "product", "market", "icp"],
            "inputVersions": {},
        },
    )
    assert response.status_code == 201
    onboarding = response.json()["data"]["onboarding"]
    assert onboarding["status"] == "draft"
    assert onboarding["activationVersion"] == 0
    assert onboarding["activatedAt"] is None


def test_workspace_activation_requires_elevated_permission_and_exact_policy_snapshot(p2d_client) -> None:
    client, _store, _launcher, _validation_launcher, _onboarding = p2d_client
    client.post(
        "/api/v1/workspace-onboarding",
        headers=headers("northstar-owner", "start-before-activation"),
        json={
            "businessPurpose": "Configure governed business truth",
            "requiredObjectTypes": ["brand", "product", "market", "icp"],
            "inputVersions": {},
        },
    )
    denied = client.post(
        "/api/v1/workspace-onboarding/activate",
        headers=headers("northstar-analyst", "denied-activation"),
        json={
            "businessPurpose": "Activate the reviewed business profile",
            "policyVersion": 3,
            "reviewedWarningCodes": [],
        },
    )
    accepted = client.post(
        "/api/v1/workspace-onboarding/activate",
        headers=headers("northstar-owner", "activate-profile"),
        json={
            "businessPurpose": "Activate the reviewed business profile",
            "policyVersion": 3,
            "reviewedWarningCodes": [],
        },
    )
    assert denied.status_code == 403
    assert accepted.status_code == 200
    onboarding = accepted.json()["data"]["onboarding"]
    assert onboarding["status"] == "active"
    assert onboarding["activationVersion"] == 1
    assert onboarding["activationSnapshot"]["policyVersion"] == 3


def test_import_routes_fail_closed_for_cross_tenant_context(p2d_client) -> None:
    client, _store, _launcher, _validation_launcher, _onboarding = p2d_client
    other_workspace = UUID("00000000-0000-4000-8000-000000000002")
    response = client.get(
        "/api/v1/import-jobs",
        headers=headers("northstar-owner", workspace_id=other_workspace),
    )
    assert response.status_code == 404


def test_mapping_and_validation_are_authorized_idempotent_background_contracts(p2d_client) -> None:
    client, store, _source_launcher, validation_launcher, _onboarding = p2d_client
    store.item = import_record("ready_for_mapping")
    mapping = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/mapping",
        headers=headers("northstar-owner", "map-products-v1"),
        json={
            "sourceFields": ["Name", "Slug", "SKU"],
            "delimiter": ",",
            "fields": [
                {"source": "Name", "target": "name", "transform": "trim"},
                {"source": "Slug", "target": "slug", "transform": "lowercase"},
                {"source": "SKU", "target": "payload.sku", "transform": "trim"},
            ],
            "businessPurpose": "Validate the approved product catalog",
        },
    )
    assert mapping.status_code == 201
    assert mapping.json()["data"]["mapping"]["version"] == 1

    validation = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/validation",
        headers=headers("northstar-owner", "validate-products-v1"),
        json={"businessPurpose": "Validate the approved product catalog"},
    )
    assert validation.status_code == 202
    assert validation.json()["data"]["job"]["status"] == "validating"
    assert len(validation_launcher.started) == 1
    assert validation_launcher.started[0][1].mapping_version_id == str(store.item.selected_mapping_version_id)

    report = client.get(
        f"/api/v1/import-jobs/{JOB_ID}/validation",
        headers=headers("northstar-analyst"),
    )
    denied = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/mapping",
        headers=headers("northstar-analyst", "denied-map"),
        json={
            "sourceFields": ["Name"],
            "delimiter": ",",
            "fields": [{"source": "Name", "target": "name"}],
            "businessPurpose": "Attempt an unauthorized import mapping",
        },
    )
    assert report.status_code == 200
    assert denied.status_code == 403

    cancelled = client.post(
        f"/api/v1/import-jobs/{JOB_ID}/cancel",
        headers=headers("northstar-owner", "cancel-validation"),
    )
    assert cancelled.status_code == 200
    assert validation_launcher.cancelled == [f"grovello-import-validate-{JOB_ID}"]
