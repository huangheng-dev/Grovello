import pytest

from grovello_workers.agents import build_growth_decision_graph


@pytest.mark.asyncio
async def test_decision_graph_preserves_evidence_and_requests_approval() -> None:
    graph = build_growth_decision_graph()
    result = await graph.ainvoke(
        {
            "workspace_id": "workspace",
            "goal": "Grow retained revenue",
            "constraints": ["Budget capped"],
            "signals": [{"source": "crm", "observedAt": "2026-07-19", "value": 12}],
        }
    )
    assert result["proposal"]["evidenceCount"] == 1
    assert result["requires_approval"] is True
