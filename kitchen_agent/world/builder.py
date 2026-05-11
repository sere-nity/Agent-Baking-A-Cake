"""Hand-assembled starting kitchens. No procedural generation."""

from __future__ import annotations

from kitchen_agent.world.schemas import Agent, Appliance, Position, World

WIDTH = 8
HEIGHT = 5


def build_kitchen_base() -> World:
    """8x5 kitchen. L-shaped counter along the top wall and right edge.

    Layout (W=width 8, H=height 5):
        y=0   F   M   T   C1  N   C2  C3  C4
        y=1   .   .   .   .   .   .   .   C5
        y=2   .   .   .   .   .   .   .   O
        y=3   .   .   .   A   .   .   .   .
        y=4   .   .   .   .   .   .   .   .

    Grid boundary handles outer walls implicitly; no internal walls.
    """
    appliances = [
        Appliance(
            id="fridge", name="fridge",
            position=Position(x=0, y=0), appliance_type="fridge",
        ),
        Appliance(
            id="microwave", name="microwave",
            position=Position(x=1, y=0), appliance_type="microwave",
        ),
        Appliance(
            id="toaster", name="toaster",
            position=Position(x=2, y=0), appliance_type="toaster",
        ),
        Appliance(
            id="counter_1", name="counter",
            position=Position(x=3, y=0), appliance_type="counter",
        ),
        Appliance(
            id="sink", name="sink",
            position=Position(x=4, y=0), appliance_type="sink",
        ),
        Appliance(
            id="counter_2", name="counter",
            position=Position(x=5, y=0), appliance_type="counter",
        ),
        Appliance(
            id="counter_3", name="counter",
            position=Position(x=6, y=0), appliance_type="counter",
        ),
        Appliance(
            id="counter_4", name="counter",
            position=Position(x=7, y=0), appliance_type="counter_corner",
        ),
        Appliance(
            id="counter_5", name="counter",
            position=Position(x=7, y=1), appliance_type="counter_side",
        ),
        Appliance(
            id="oven", name="oven",
            position=Position(x=7, y=2), appliance_type="oven",
        ),
    ]

    return World(
        width=WIDTH,
        height=HEIGHT,
        walls=set(),
        entities={a.id: a for a in appliances},
        agent=Agent(position=Position(x=3, y=3)),
        goal="",
    )


if __name__ == "__main__":
    print(build_kitchen_base().model_dump_json(indent=2))
