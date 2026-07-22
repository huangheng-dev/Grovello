import pytest

from grovello.temporal_asset_verification import TemporalAssetVerificationLauncher


@pytest.mark.asyncio
async def test_cancel_uses_native_temporal_cancellation() -> None:
    class Handle:
        def __init__(self) -> None:
            self.cancelled = False

        async def cancel(self) -> None:
            self.cancelled = True

    handle = Handle()

    class Client:
        def get_workflow_handle(self, workflow_id: str):
            assert workflow_id == "grovello-asset-verify-workspace-upload"
            return handle

    launcher = TemporalAssetVerificationLauncher("unused", "default", "queue")
    launcher._client = Client()
    await launcher.cancel("grovello-asset-verify-workspace-upload")
    assert handle.cancelled is True
