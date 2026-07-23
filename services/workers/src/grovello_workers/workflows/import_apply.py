from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from grovello.import_apply_activity import (
        apply_import_change_set,
        compensate_import_change_set,
        fail_import_apply,
        fail_import_compensation,
    )
    from grovello.import_change_sets import ImportApplyInput


@workflow.defn(name="grovello-import-apply")
class ImportApplyWorkflow:
    def __init__(self) -> None:
        self._status = "pending"

    @workflow.run
    async def run(self, payload: ImportApplyInput) -> str:
        self._status = "applying"
        try:
            result = await workflow.execute_activity(
                apply_import_change_set,
                payload,
                start_to_close_timeout=timedelta(minutes=30),
                heartbeat_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3,
                ),
            )
        except ActivityError:
            result = await workflow.execute_activity(
                fail_import_apply,
                payload,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        self._status = result
        return result

    @workflow.query(name="status")
    def status(self) -> str:
        return self._status


@workflow.defn(name="grovello-import-compensation")
class ImportCompensationWorkflow:
    def __init__(self) -> None:
        self._status = "pending"

    @workflow.run
    async def run(self, payload: ImportApplyInput) -> str:
        self._status = "compensating"
        try:
            result = await workflow.execute_activity(
                compensate_import_change_set,
                payload,
                start_to_close_timeout=timedelta(minutes=30),
                heartbeat_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=2),
                    maximum_interval=timedelta(seconds=30),
                    maximum_attempts=3,
                ),
            )
        except ActivityError:
            result = await workflow.execute_activity(
                fail_import_compensation,
                payload,
                start_to_close_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        self._status = result
        return result

    @workflow.query(name="status")
    def status(self) -> str:
        return self._status
