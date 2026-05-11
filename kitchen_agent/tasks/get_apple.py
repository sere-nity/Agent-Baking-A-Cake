"""Trivial insurance task: fetch an apple from the fridge."""

from __future__ import annotations

from kitchen_agent.world.builder import build_kitchen_base
from kitchen_agent.world.schemas import Appliance, Ingredient, World

GOAL = "Bring me the apple."


def starting_world() -> World:
    world = build_kitchen_base()
    world.goal = GOAL

    apple = Ingredient(id="apple_1", food="apple", name="apple", in_id="fridge")
    fridge = world.entities["fridge"]
    assert isinstance(fridge, Appliance)
    fridge.contents.append(apple.id)
    world.entities[apple.id] = apple

    return world


def is_goal_met(world: World) -> bool:
    return "apple_1" in (world.agent.left_hand, world.agent.right_hand)


if __name__ == "__main__":
    print(starting_world().model_dump_json(indent=2))
