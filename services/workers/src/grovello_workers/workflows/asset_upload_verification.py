from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from grovello.asset_scan_activity import fail_asset_scan, scan_asset_upload
    from grovello.asset_uploads import AssetVerificationInput
    from grovello.asset_verification_activity import verify_asset_upload


@workflow.defn(name="grovello-asset-upload-verification")
class AssetUploadVerificationWorkflow:
    def __init__(self) -> None:
        self._cancelled = False
        self._status = "pending"

    @workflow.run
    async def run(self, payload: AssetVerificationInput) -> str:
        if self._cancelled:
            return "cancelled"
        self._status = "verifying"
        result = await workflow.execute_activity(
            verify_asset_upload,
            payload,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=5,
            ),
        )
        if self._cancelled or result == "cancelled":
            self._status = "cancelled"
            return self._status
        self._status = "scanning"
        try:
            result = await workflow.execute_activity(
                scan_asset_upload,
                payload,
                start_to_close_timeout=timedelta(minutes=5),
                heartbeat_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    maximum_interval=timedelta(minutes=1),
                    maximum_attempts=3,
                ),
            )
        except ActivityError:
            result = await workflow.execute_activity(
                fail_asset_scan,
                payload,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        self._status = "cancelled" if self._cancelled else result
        return self._status

    @workflow.signal(name="cancel")
    async def cancel(self) -> None:
        self._cancelled = True
        self._status = "cancelled"

    @workflow.query(name="status")
    def status(self) -> str:
        return self._status
