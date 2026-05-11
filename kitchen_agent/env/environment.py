"""KitchenEnv — wires task starting worlds, transitions, and observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import numpy as np

from kitchen_agent.env import transitions
from kitchen_agent.env.observation import Observation, build_observation
from kitchen_agent.world.schemas import ActionRecord, World


class Task(Protocol):
    def starting_world(self) -> World: ...
    def is_goal_met(self, world: World) -> bool: ...


@dataclass
class StepResult:
    observation: Observation
    success: bool
    message: str
    done: bool
    info: dict[str, Any] = field(default_factory=dict)


_HANDLERS: dict[str, Callable[..., tuple[bool, str]]] = {
    "navigate_to": transitions.navigate_to,
    "pick_up": transitions.pick_up,
    "place": transitions.place,
    "pour": transitions.pour,
    "whisk": transitions.whisk,
    "set_appliance": transitions.set_appliance,
    "wait": transitions.wait,
}


class KitchenEnv:
    def __init__(self, task: Task) -> None:
        self.task = task
        self._world: World | None = None

    @property
    def world(self) -> World:
        if self._world is None:
            raise RuntimeError("Env not started; call reset() first.")
        return self._world

    def reset(self) -> Observation:
        self._world = self.task.starting_world()
        return self.observe()

    def step(self, tool_name: str, tool_args: dict[str, Any]) -> StepResult:
        world = self.world
        handler = _HANDLERS.get(tool_name)
        if handler is None:
            available = ", ".join(_HANDLERS)
            success, message = False, (
                f"Unknown action '{tool_name}'. Available: {available}."
            )
        else:
            try:
                success, message = handler(world, **tool_args)
            except TypeError as e:
                success, message = False, (
                    f"Bad arguments for '{tool_name}': {e}"
                )

        world.history.append(
            ActionRecord(
                t=world.t,
                action=tool_name,
                args=dict(tool_args),
                success=success,
                message=message,
            )
        )

        return StepResult(
            observation=self.observe(),
            success=success,
            message=message,
            done=self.is_goal_met(),
        )

    def observe(self) -> Observation:
        return build_observation(self.world)

    def render(self) -> np.ndarray | None:
        return None

    def is_goal_met(self) -> bool:
        if self._world is None:
            return False
        return self.task.is_goal_met(self._world)

    @property
    def available_actions(self) -> list[dict[str, Any]]:
        return self.observe().available_actions
