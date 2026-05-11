"""Headline task: bake a cake from raw ingredients."""

from __future__ import annotations

from kitchen_agent.world.builder import build_kitchen_base
from kitchen_agent.world.schemas import (
    Appliance,
    Container,
    CookState,
    Ingredient,
    World,
)

GOAL = "Bake a cake."


def starting_world() -> World:
    world = build_kitchen_base()
    world.goal = GOAL

    fridge_items = [
        Ingredient(id="egg_1", food="egg", name="egg", in_id="fridge"),
        Ingredient(id="butter_1", food="butter", name="butter", in_id="fridge"),
        Ingredient(id="milk_1", food="milk", name="milk", in_id="fridge"),
    ]
    # Dry goods on the corner counter (no pantry in this layout).
    dry_goods_items = [
        Ingredient(id="flour_1", food="flour", name="flour", in_id="counter_3"),
        Ingredient(id="sugar_1", food="sugar", name="sugar", in_id="counter_3"),
    ]
    # Cake tools on the central counter.
    counter_items = [
        Container(
            id="mixing_bowl", name="mixing bowl",
            container_type="bowl", in_id="counter_2",
        ),
        Container(
            id="whisk_1", name="whisk",
            container_type="whisk", in_id="counter_2",
        ),
        Container(
            id="cake_tin", name="cake tin",
            container_type="tin", in_id="counter_2",
        ),
    ]

    fridge = world.entities["fridge"]
    counter_2 = world.entities["counter_2"]
    counter_3 = world.entities["counter_3"]
    assert isinstance(fridge, Appliance)
    assert isinstance(counter_2, Appliance)
    assert isinstance(counter_3, Appliance)

    for ent in fridge_items:
        world.entities[ent.id] = ent
        fridge.contents.append(ent.id)
    for ent in dry_goods_items:
        world.entities[ent.id] = ent
        counter_3.contents.append(ent.id)
    for ent in counter_items:
        world.entities[ent.id] = ent
        counter_2.contents.append(ent.id)

    return world


def is_goal_met(world: World) -> bool:
    cake_tin = world.entities.get("cake_tin")
    if not isinstance(cake_tin, Container):
        return False
    for content_id in cake_tin.contents:
        ent = world.entities.get(content_id)
        if (
            isinstance(ent, Ingredient)
            and ent.food == "batter"
            and ent.cook_state == CookState.COOKED
        ):
            return True
    return False


if __name__ == "__main__":
    print(starting_world().model_dump_json(indent=2))
