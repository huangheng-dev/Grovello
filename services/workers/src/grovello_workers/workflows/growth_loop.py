from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

from grovello_workers.workflows.contracts import GrowthLoopInput, GrowthLoopStatus

with workflow.unsafe.imports_passed_through():
    from grovello_workers.activities.growth import execute_growth_action, prepare_growth_decision


@workflow.defn
class GrowthLoopWorkflow:
    def __init__(self) -> None:
        self.state = GrowthLoopStatus()

    @workflow.run
    async def run(self, payload: GrowthLoopInput) -> GrowthLoopStatus:
        retry = RetryPolicy(
            initial_interval=timedelta(seconds=2), maximum_interval=timedelta(minutes=2), maximum_attempts=5
        )
        self.state.phase = "reasoning"
        self.state.proposal = await workflow.execute_activity(
            prepare_growth_decision,
            payload,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=retry,
        )
        if self.state.proposal.get("requiresApproval", True):
            self.state.phase = "awaiting_approval"
            await workflow.wait_condition(lambda: self.state.approved or self.state.cancelled)
        if self.state.cancelled:
            self.state.phase = "cancelled"
            return self.state
        self.state.phase = "executing"
        self.state.result = await workflow.execute_activity(
            execute_growth_action,
            args=[payload.workspace_id, self.state.proposal],
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=retry,
        )
        self.state.phase = "completed"
        return self.state

    @workflow.signal
    async def approve(self) -> None:
        self.state.approved = True

    @workflow.signal
    async def cancel(self) -> None:
        self.state.cancelled = True

    @workflow.query
    def status(self) -> GrowthLoopStatus:
        return self.state
