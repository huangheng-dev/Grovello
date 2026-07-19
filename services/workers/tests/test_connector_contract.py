import pytest

from grovello_workers.connectors import (
    Connector,
    ConnectorCapability,
    ConnectorContext,
    ConnectorManifest,
    ConnectorResult,
    ConnectorRisk,
)


class FakePublisher(Connector):
    manifest = ConnectorManifest(
        key="fake-publisher",
        version="1.0.0",
        display_name="Fake Publisher",
        provider="test",
        capabilities={ConnectorCapability.PUBLISH},
        risks={ConnectorRisk.EXTERNAL_WRITE},
        supports_idempotency=True,
    )

    async def health(self) -> ConnectorResult:
        return ConnectorResult(succeeded=True)

    async def execute(self, capability, payload, context):
        self.validate_execution(capability, context)
        return ConnectorResult(succeeded=True, external_id="external-1")


@pytest.mark.asyncio
async def test_external_write_requires_approval() -> None:
    connector = FakePublisher()
    context = ConnectorContext(
        workspace_id="workspace", actor_id="user", run_id="run", idempotency_key="key", dry_run=False
    )
    with pytest.raises(PermissionError):
        await connector.execute(ConnectorCapability.PUBLISH, {}, context)


@pytest.mark.asyncio
async def test_approved_external_write_can_execute() -> None:
    connector = FakePublisher()
    context = ConnectorContext(
        workspace_id="workspace",
        actor_id="user",
        run_id="run",
        idempotency_key="key",
        dry_run=False,
        approved=True,
    )
    result = await connector.execute(ConnectorCapability.PUBLISH, {}, context)
    assert result.succeeded is True
