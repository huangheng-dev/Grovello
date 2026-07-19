from typing import Any

from temporalio import activity

from grovello_workers.agents import build_growth_decision_graph
from grovello_workers.workflows.contracts import GrowthLoopInput


@activity.defn
async def prepare_growth_decision(payload: GrowthLoopInput) -> dict[str, Any]:
    graph = build_growth_decision_graph()
    result = await graph.ainvoke(
        {
            "workspace_id": payload.workspace_id,
            "goal": payload.goal,
            "constraints": payload.constraints,
            "signals": payload.signals,
        }
    )
    return {**result.get("proposal", {}), "requiresApproval": result.get("requires_approval", True)}


@activity.defn
async def execute_growth_action(workspace_id: str, proposal: dict[str, Any]) -> dict[str, Any]:
    # Foundation behavior is deliberately dry-run. A connector registry is required for external writes.
    return {"workspaceId": workspace_id, "status": "dry_run", "proposal": proposal}
