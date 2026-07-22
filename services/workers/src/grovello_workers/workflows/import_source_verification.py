from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from grovello.business_imports import ImportSourceVerificationInput
    from grovello.import_source_activity import (
        fail_import_source_scan,
        scan_import_source,
        verify_import_source,
    )


@workflow.defn(name="grovello-import-source-verification")
class ImportSourceVerificationWorkflow:
    def __init__(self) -> None:
        self._status = "pending"

    @workflow.run
    async def run(self, payload: ImportSourceVerificationInput) -> str:
        self._status = "verifying"
        result = await workflow.execute_activity(
            verify_import_source,
            payload,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=30),
                maximum_attempts=5,
            ),
        )
        if result == "cancelled":
            self._status = "cancelled"
            return self._status
        self._status = "scanning"
        try:
            result = await workflow.execute_activity(
                scan_import_source,
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
                fail_import_source_scan,
                payload,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        self._status = result
        return result

    @workflow.query(name="status")
    def status(self) -> str:
        return self._status
