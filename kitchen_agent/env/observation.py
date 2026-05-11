"""Observation. Stub for Phase 3 — Phase 4 builds the proper text format."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kitchen_agent.world.schemas import World


@dataclass
class Observation:
    text: str
    available_actions: list[dict[str, Any]] = field(default_factory=list)


def build_observation(world: World) -> Observation:
    p = world.agent.position
    return Observation(
        text=(
            f"t={world.t} | goal: {world.goal} | "
            f"agent at ({p.x},{p.y}) facing {world.agent.facing.value} | "
            f"hands_free={world.agent.hands_free}"
        )
    )
