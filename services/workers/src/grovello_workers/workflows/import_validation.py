from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from grovello.business_imports import ImportValidationInput
    from grovello.import_validation_activity import fail_import_validation, validate_import


@workflow.defn(name="grovello-import-validation")
class ImportValidationWorkflow:
    def __init__(self) -> None:
        self._status = "pending"

    @workflow.run
    async def run(self, payload: ImportValidationInput) -> str:
        self._status = "validating"
        try:
            result = await workflow.execute_activity(
                validate_import,
                payload,
                start_to_close_timeout=timedelta(minutes=15),
                heartbeat_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3,
                ),
            )
        except ActivityError:
            result = await workflow.execute_activity(
                fail_import_validation,
                payload,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        self._status = result
        return result

    @workflow.query(name="status")
    def status(self) -> str:
        return self._status
