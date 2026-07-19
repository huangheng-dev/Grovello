from dataclasses import dataclass, field
from typing import Any


@dataclass
class GrowthLoopInput:
    workspace_id: str
    goal: str
    constraints: list[str] = field(default_factory=list)
    signals: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GrowthLoopStatus:
    phase: str = "received"
    approved: bool = False
    cancelled: bool = False
    proposal: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
