from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from grovello.asset_finalization import AssetFinalizationInput
    from grovello.asset_finalization_activity import (
        cleanup_finalized_asset_staging,
        commit_asset_finalization,
        compensate_asset_promotion,
        fail_asset_finalization,
        mark_asset_staging_cleanup_failed,
        promote_asset_upload,
    )


@workflow.defn(name="grovello-asset-finalization")
class AssetFinalizationWorkflow:
    def __init__(self) -> None:
        self._status = "requested"

    @workflow.run
    async def run(self, payload: AssetFinalizationInput) -> str:
        self._status = "promoting"
        try:
            promoted = await workflow.execute_activity(
                promote_asset_upload,
                payload,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=5,
                ),
            )
        except ActivityError:
            self._status = await workflow.execute_activity(
                fail_asset_finalization,
                payload,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            return self._status

        self._status = "committing"
        try:
            await workflow.execute_activity(
                commit_asset_finalization,
                (payload, promoted),
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=20),
                    maximum_attempts=5,
                ),
            )
        except ActivityError:
            self._status = await workflow.execute_activity(
                compensate_asset_promotion,
                (payload, promoted),
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=10),
            )
            return self._status

        self._status = "cleaning_staging"
        try:
            self._status = await workflow.execute_activity(
                cleanup_finalized_asset_staging,
                payload,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=10,
                ),
            )
        except ActivityError:
            self._status = await workflow.execute_activity(
                mark_asset_staging_cleanup_failed,
                payload,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
        return self._status

    @workflow.query(name="status")
    def status(self) -> str:
        return self._status
