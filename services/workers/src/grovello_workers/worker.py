import asyncio

from grovello.asset_finalization_activity import (
    cleanup_finalized_asset_staging,
    commit_asset_finalization,
    compensate_asset_promotion,
    fail_asset_finalization,
    mark_asset_staging_cleanup_failed,
    promote_asset_upload,
)
from grovello.asset_scan_activity import fail_asset_scan, scan_asset_upload
from grovello.asset_verification_activity import verify_asset_upload
from grovello.import_apply_activity import (
    apply_import_change_set,
    compensate_import_change_set,
    fail_import_apply,
    fail_import_compensation,
)
from grovello.import_source_activity import (
    fail_import_source_scan,
    scan_import_source,
    verify_import_source,
)
from grovello.import_validation_activity import fail_import_validation, validate_import
from temporalio.client import Client
from temporalio.worker import Worker

from grovello_workers.activities.growth import execute_growth_action, prepare_growth_decision
from grovello_workers.settings import get_settings
from grovello_workers.workflows.asset_finalization import AssetFinalizationWorkflow
from grovello_workers.workflows.asset_upload_verification import AssetUploadVerificationWorkflow
from grovello_workers.workflows.growth_loop import GrowthLoopWorkflow
from grovello_workers.workflows.import_apply import ImportApplyWorkflow, ImportCompensationWorkflow
from grovello_workers.workflows.import_source_verification import ImportSourceVerificationWorkflow
from grovello_workers.workflows.import_validation import ImportValidationWorkflow


async def run_worker() -> None:
    settings = get_settings()
    client = await Client.connect(settings.temporal_address, namespace=settings.temporal_namespace)
    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[
            GrowthLoopWorkflow,
            AssetUploadVerificationWorkflow,
            AssetFinalizationWorkflow,
            ImportSourceVerificationWorkflow,
            ImportValidationWorkflow,
            ImportApplyWorkflow,
            ImportCompensationWorkflow,
        ],
        activities=[
            prepare_growth_decision,
            execute_growth_action,
            verify_asset_upload,
            scan_asset_upload,
            fail_asset_scan,
            promote_asset_upload,
            commit_asset_finalization,
            cleanup_finalized_asset_staging,
            compensate_asset_promotion,
            fail_asset_finalization,
            mark_asset_staging_cleanup_failed,
            verify_import_source,
            scan_import_source,
            fail_import_source_scan,
            validate_import,
            fail_import_validation,
            apply_import_change_set,
            compensate_import_change_set,
            fail_import_apply,
            fail_import_compensation,
        ],
    )
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
