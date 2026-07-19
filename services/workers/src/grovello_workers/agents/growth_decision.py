from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph


class GrowthDecisionState(TypedDict, total=False):
    workspace_id: str
    goal: str
    constraints: list[str]
    signals: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    proposal: dict[str, Any]
    risk_level: str
    requires_approval: bool


def collect_evidence(state: GrowthDecisionState) -> GrowthDecisionState:
    verified = [
        signal for signal in state.get("signals", []) if signal.get("source") and signal.get("observedAt")
    ]
    return {**state, "evidence": verified}


def propose_action(state: GrowthDecisionState) -> GrowthDecisionState:
    evidence = state.get("evidence", [])
    proposal = {
        "objective": state.get("goal", "Review growth opportunity"),
        "evidenceCount": len(evidence),
        "expectedOutcome": "Create a measurable, reversible experiment before scaling.",
        "nextStep": "human_review" if not evidence else "policy_evaluation",
    }
    return {**state, "proposal": proposal, "risk_level": "medium" if evidence else "high"}


def evaluate_risk(state: GrowthDecisionState) -> GrowthDecisionState:
    constraints = state.get("constraints", [])
    requires_approval = state.get("risk_level") != "low" or bool(constraints)
    return {**state, "requires_approval": requires_approval}


def build_growth_decision_graph():
    graph = StateGraph(GrowthDecisionState)
    graph.add_node("collect_evidence", collect_evidence)
    graph.add_node("propose_action", propose_action)
    graph.add_node("evaluate_risk", evaluate_risk)
    graph.add_edge(START, "collect_evidence")
    graph.add_edge("collect_evidence", "propose_action")
    graph.add_edge("propose_action", "evaluate_risk")
    graph.add_edge("evaluate_risk", END)
    return graph.compile()
