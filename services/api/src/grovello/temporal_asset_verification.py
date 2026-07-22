import asyncio

from temporalio.client import Client, WorkflowHandle
from temporalio.exceptions import WorkflowAlreadyStartedError

from grovello.asset_uploads import AssetVerificationInput, AssetVerificationLauncher


class TemporalAssetVerificationLauncher(AssetVerificationLauncher):
    def __init__(self, address: str, namespace: str, task_queue: str) -> None:
        self._address = address
        self._namespace = namespace
        self._task_queue = task_queue
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    async def start(self, workflow_id: str, payload: AssetVerificationInput) -> None:
        client = await self._get_client()
        try:
            await client.start_workflow(
                "grovello-asset-upload-verification",
                payload,
                id=workflow_id,
                task_queue=self._task_queue,
            )
        except WorkflowAlreadyStartedError:
            return

    async def cancel(self, workflow_id: str) -> None:
        client = await self._get_client()
        handle: WorkflowHandle = client.get_workflow_handle(workflow_id)
        await handle.cancel()

    async def _get_client(self) -> Client:
        if self._client is not None:
            return self._client
        async with self._lock:
            if self._client is None:
                self._client = await Client.connect(self._address, namespace=self._namespace)
        return self._client
