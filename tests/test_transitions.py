"""One test per action: preconditions, success cases, message quality.
No imports of pygame or anthropic in this file."""

from __future__ import annotations

import pytest

from kitchen_agent.env.transitions import (
    BATTER_RECIPE,
    navigate_to,
    pick_up,
    place,
    pour,
    set_appliance,
    wait,
    whisk,
)
from kitchen_agent.world.builder import build_kitchen_base
from kitchen_agent.world.schemas import (
    Appliance,
    Container,
    CookState,
    Facing,
    Ingredient,
    Position,
    Setting,
    World,
)

# ----- fixtures / helpers ----------------------------------------------------


def _add_ingredient(world: World, ing_id: str, food: str, in_id: str) -> Ingredient:
    ing = Ingredient(id=ing_id, food=food, name=food, in_id=in_id)
    world.entities[ing_id] = ing
    parent = world.entities[in_id]
    assert isinstance(parent, (Appliance, Container))
    parent.contents.append(ing_id)
    return ing


def _add_container(world: World, cid: str, name: str, in_id: str) -> Container:
    c = Container(id=cid, name=name, in_id=in_id)
    world.entities[cid] = c
    parent = world.entities[in_id]
    assert isinstance(parent, Appliance)
    parent.contents.append(cid)
    return c


def _agent_holds(world: World, entity_id: str) -> None:
    ent = world.entities[entity_id]
    assert not isinstance(ent, Appliance)
    if ent.in_id is not None:
        parent = world.entities.get(ent.in_id)
        if parent is not None and not isinstance(parent, Ingredient):
            if entity_id in parent.contents:
                parent.contents.remove(entity_id)
    ent.in_id = None
    if world.agent.left_hand is None:
        world.agent.left_hand = entity_id
    elif world.agent.right_hand is None:
        world.agent.right_hand = entity_id
    else:
        raise RuntimeError("both hands full")


@pytest.fixture
def world() -> World:
    """Base kitchen with one apple in fridge."""
    w = build_kitchen_base()
    _add_ingredient(w, "apple_1", "apple", "fridge")
    return w


# ----- navigate_to -----------------------------------------------------------


class TestNavigateTo:
    def test_success_moves_agent_to_adjacent_tile_and_faces_target(
        self, world: World
    ) -> None:
        # Agent starts at (3,3); fridge is at (0,0).
        ok, msg = navigate_to(world, "fridge")
        assert ok, msg
        # Destination must be one of fridge's walkable neighbours.
        ax, ay = world.agent.position.x, world.agent.position.y
        assert (ax, ay) in {(0, 1)}  # only walkable neighbour of (0,0)
        assert world.agent.facing == Facing.NORTH  # fridge is above
        assert "navigated" in msg.lower()
        assert "steps" in msg

    def test_already_adjacent_does_not_move(self, world: World) -> None:
        world.agent.position = Position(x=0, y=1)
        ok, msg = navigate_to(world, "fridge")
        assert ok
        assert world.agent.position == Position(x=0, y=1)
        assert world.agent.facing == Facing.NORTH
        assert "already adjacent" in msg.lower()

    def test_unknown_target(self, world: World) -> None:
        ok, msg = navigate_to(world, "nope")
        assert not ok
        assert "nope" in msg

    def test_target_with_no_anchor_fails(self, world: World) -> None:
        """An ingredient with no in_id has no walkable target."""
        floating = Ingredient(id="ghost", food="ghost", name="ghost", in_id=None)
        world.entities["ghost"] = floating
        ok, msg = navigate_to(world, "ghost")
        assert not ok
        assert "no fixed position" in msg.lower()

    def test_held_target_fails(self, world: World) -> None:
        _agent_holds(world, "apple_1")
        ok, msg = navigate_to(world, "apple_1")
        assert not ok
        assert "holding" in msg.lower()


# ----- pick_up ---------------------------------------------------------------


class TestPickUp:
    def test_success(self, world: World) -> None:
        world.agent.position = Position(x=0, y=1)  # adjacent to fridge
        ok, msg = pick_up(world, "apple_1")
        assert ok, msg
        assert world.agent.left_hand == "apple_1"
        assert world.entities["apple_1"].in_id is None
        assert "apple_1" not in world.entities["fridge"].contents  # type: ignore[union-attr]
        assert "picked up" in msg.lower()

    def test_not_adjacent_message_includes_positions_and_hint(
        self, world: World
    ) -> None:
        # Agent at (3,3); apple_1 is in fridge at (0,0). Not adjacent.
        ok, msg = pick_up(world, "apple_1")
        assert not ok
        assert "not adjacent" in msg.lower()
        assert "(3,3)" in msg
        assert "(0,0)" in msg
        assert "navigate_to" in msg

    def test_appliance_cannot_be_picked_up(self, world: World) -> None:
        world.agent.position = Position(x=0, y=1)
        ok, msg = pick_up(world, "fridge")
        assert not ok
        assert "fixed" in msg.lower() or "appliance" in msg.lower()

    def test_unknown_entity(self, world: World) -> None:
        ok, msg = pick_up(world, "missing")
        assert not ok
        assert "missing" in msg

    def test_both_hands_full(self, world: World) -> None:
        world.agent.position = Position(x=0, y=1)
        # Manually fill both hands.
        bowl = Container(id="bowl_x", name="bowl", in_id=None)
        whisk_c = Container(id="whisk_x", name="whisk", in_id=None)
        world.entities["bowl_x"] = bowl
        world.entities["whisk_x"] = whisk_c
        world.agent.left_hand = "bowl_x"
        world.agent.right_hand = "whisk_x"
        ok, msg = pick_up(world, "apple_1")
        assert not ok
        assert "both hands" in msg.lower()
        assert "place" in msg.lower()  # hint to free a hand

    def test_already_holding(self, world: World) -> None:
        _agent_holds(world, "apple_1")
        ok, msg = pick_up(world, "apple_1")
        assert not ok
        assert "already holding" in msg.lower()


# ----- place -----------------------------------------------------------------


class TestPlace:
    def test_ingredient_into_container_success(self, world: World) -> None:
        # Put a bowl on counter_2; agent adjacent to counter_2; agent holding apple.
        _add_container(world, "bowl_1", "bowl", "counter_2")
        world.agent.position = Position(x=5, y=1)  # south of counter_2 at (5,0)
        _agent_holds(world, "apple_1")
        ok, msg = place(world, "apple_1", "bowl_1")
        assert ok, msg
        assert world.entities["apple_1"].in_id == "bowl_1"
        assert "apple_1" in world.entities["bowl_1"].contents  # type: ignore[union-attr]
        assert world.agent.left_hand is None and world.agent.right_hand is None

    def test_container_onto_appliance_success(self, world: World) -> None:
        bowl = Container(id="bowl_1", name="bowl", in_id=None)
        world.entities["bowl_1"] = bowl
        world.agent.position = Position(x=5, y=1)
        world.agent.left_hand = "bowl_1"
        ok, msg = place(world, "bowl_1", "counter_2")
        assert ok, msg
        assert bowl.in_id == "counter_2"
        assert "bowl_1" in world.entities["counter_2"].contents  # type: ignore[union-attr]

    def test_not_holding(self, world: World) -> None:
        world.agent.position = Position(x=0, y=1)
        ok, msg = place(world, "apple_1", "fridge")
        assert not ok
        assert "not holding" in msg.lower()

    def test_not_adjacent_to_target(self, world: World) -> None:
        _agent_holds(world, "apple_1")
        # Agent still at (3,3); fridge at (0,0) — not adjacent.
        ok, msg = place(world, "apple_1", "fridge")
        assert not ok
        assert "not adjacent" in msg.lower()
        assert "navigate_to" in msg

    def test_target_is_ingredient_rejected(self, world: World) -> None:
        _add_ingredient(world, "apple_2", "apple", "fridge")
        _agent_holds(world, "apple_1")
        world.agent.position = Position(x=0, y=1)
        ok, msg = place(world, "apple_1", "apple_2")
        assert not ok
        assert "ingredient" in msg.lower()

    def test_container_into_container_rejected(self, world: World) -> None:
        _add_container(world, "bowl_inner", "small bowl", "counter_2")
        _add_container(world, "bowl_outer", "big bowl", "counter_3")
        _agent_holds(world, "bowl_inner")
        world.agent.position = Position(x=5, y=1)  # adjacent to counter_2 only
        # Reposition to be adjacent to bowl_outer (which is on counter_3 at (6,0))
        world.agent.position = Position(x=6, y=1)
        ok, msg = place(world, "bowl_inner", "bowl_outer")
        assert not ok
        assert "nest" in msg.lower()


# ----- pour ------------------------------------------------------------------


class TestPour:
    def test_success_transfers_all_contents(self, world: World) -> None:
        bowl = Container(id="bowl_1", name="bowl", in_id=None)
        tin = Container(id="tin_1", name="tin", in_id="counter_2")
        world.entities["bowl_1"] = bowl
        world.entities["tin_1"] = tin
        world.entities["counter_2"].contents.append("tin_1")  # type: ignore[union-attr]
        # Put two ingredients into the held bowl.
        for ing_id, food in [("flour_1", "flour"), ("sugar_1", "sugar")]:
            ing = Ingredient(
                id=ing_id, food=food, name=food, in_id="bowl_1"
            )
            world.entities[ing_id] = ing
            bowl.contents.append(ing_id)
        world.agent.left_hand = "bowl_1"
        world.agent.position = Position(x=5, y=1)
        ok, msg = pour(world, "bowl_1", "tin_1")
        assert ok, msg
        assert bowl.contents == []
        assert set(tin.contents) == {"flour_1", "sugar_1"}
        assert world.entities["flour_1"].in_id == "tin_1"
        assert "2" in msg  # count

    def test_source_not_held(self, world: World) -> None:
        _add_container(world, "bowl_1", "bowl", "counter_2")
        _add_container(world, "tin_1", "tin", "counter_3")
        world.agent.position = Position(x=5, y=1)
        ok, msg = pour(world, "bowl_1", "tin_1")
        assert not ok
        assert "hold" in msg.lower()

    def test_source_empty(self, world: World) -> None:
        bowl = Container(id="bowl_1", name="bowl", in_id=None)
        world.entities["bowl_1"] = bowl
        world.agent.left_hand = "bowl_1"
        _add_container(world, "tin_1", "tin", "counter_2")
        world.agent.position = Position(x=5, y=1)
        ok, msg = pour(world, "bowl_1", "tin_1")
        assert not ok
        assert "empty" in msg.lower()

    def test_target_not_adjacent(self, world: World) -> None:
        bowl = Container(id="bowl_1", name="bowl", in_id=None)
        world.entities["bowl_1"] = bowl
        world.entities["bowl_1"].contents.append("apple_1")  # type: ignore[union-attr]
        world.entities["apple_1"].in_id = "bowl_1"
        world.entities["fridge"].contents.remove("apple_1")  # type: ignore[union-attr]
        world.agent.left_hand = "bowl_1"
        _add_container(world, "tin_1", "tin", "counter_2")
        # Agent at (3,3) — not adjacent to counter_2 at (5,0).
        ok, msg = pour(world, "bowl_1", "tin_1")
        assert not ok
        assert "not adjacent" in msg.lower()

    def test_source_not_a_container(self, world: World) -> None:
        _agent_holds(world, "apple_1")
        world.agent.position = Position(x=5, y=1)
        _add_container(world, "tin_1", "tin", "counter_2")
        ok, msg = pour(world, "apple_1", "tin_1")
        assert not ok
        assert "container" in msg.lower()


# ----- whisk -----------------------------------------------------------------


class TestWhisk:
    def test_success_sets_whisked_flag(self, world: World) -> None:
        _add_container(world, "bowl_1", "bowl", "counter_2")
        world.agent.position = Position(x=5, y=1)
        ok, msg = whisk(world, "bowl_1")
        assert ok, msg
        bowl = world.entities["bowl_1"]
        assert isinstance(bowl, Container)
        assert bowl.contents_whisked is True

    def test_full_recipe_transforms_into_batter(self, world: World) -> None:
        _add_container(world, "bowl_1", "bowl", "counter_2")
        for food in BATTER_RECIPE:
            _add_ingredient(world, f"{food}_x", food, "bowl_1")
        world.agent.position = Position(x=5, y=1)
        ok, msg = whisk(world, "bowl_1")
        assert ok, msg
        bowl = world.entities["bowl_1"]
        assert isinstance(bowl, Container)
        # Only batter remains inside.
        kids = [world.entities[c] for c in bowl.contents]
        assert len(kids) == 1
        assert isinstance(kids[0], Ingredient)
        assert kids[0].food == "batter"
        # Recipe ingredients deleted from world.
        for food in BATTER_RECIPE:
            assert f"{food}_x" not in world.entities
        assert "batter" in msg.lower()

    def test_incomplete_recipe_lists_missing(self, world: World) -> None:
        _add_container(world, "bowl_1", "bowl", "counter_2")
        _add_ingredient(world, "egg_x", "egg", "bowl_1")
        _add_ingredient(world, "flour_x", "flour", "bowl_1")
        world.agent.position = Position(x=5, y=1)
        ok, msg = whisk(world, "bowl_1")
        assert ok, msg
        # No batter created.
        assert "batter" not in world.entities
        # Missing items listed.
        for missing in ("butter", "milk", "sugar"):
            assert missing in msg.lower()

    def test_non_container_rejected(self, world: World) -> None:
        world.agent.position = Position(x=0, y=1)
        ok, msg = whisk(world, "apple_1")
        assert not ok
        assert "container" in msg.lower()

    def test_not_adjacent_and_not_held(self, world: World) -> None:
        _add_container(world, "bowl_1", "bowl", "counter_2")
        # Agent stays at (3,3); counter_2 is at (5,0).
        ok, msg = whisk(world, "bowl_1")
        assert not ok
        assert "adjacent" in msg.lower() or "held" in msg.lower()


# ----- set_appliance ---------------------------------------------------------


class TestSetAppliance:
    def test_success(self, world: World) -> None:
        world.agent.position = Position(x=6, y=2)  # adjacent to oven at (7,2)
        ok, msg = set_appliance(world, "oven", "high")
        assert ok, msg
        oven = world.entities["oven"]
        assert isinstance(oven, Appliance)
        assert oven.setting == Setting.HIGH
        assert "high" in msg.lower()

    def test_not_adjacent(self, world: World) -> None:
        ok, msg = set_appliance(world, "oven", "high")
        assert not ok
        assert "not adjacent" in msg.lower()
        assert "navigate_to" in msg

    def test_invalid_setting(self, world: World) -> None:
        world.agent.position = Position(x=6, y=2)
        ok, msg = set_appliance(world, "oven", "BLAZING")
        assert not ok
        assert "invalid" in msg.lower()
        # Lists valid options.
        for s in ("off", "low", "medium", "high"):
            assert s in msg

    def test_non_appliance_rejected(self, world: World) -> None:
        ok, msg = set_appliance(world, "apple_1", "high")
        assert not ok
        assert "not an appliance" in msg.lower()


# ----- wait ------------------------------------------------------------------


class TestWait:
    def test_advances_time(self, world: World) -> None:
        ok, msg = wait(world, 5)
        assert ok, msg
        assert world.t == 5
        assert "t=5" in msg

    def test_non_positive_rejected(self, world: World) -> None:
        ok, msg = wait(world, 0)
        assert not ok
        ok2, msg2 = wait(world, -3)
        assert not ok2
        assert "positive" in msg.lower()

    def test_ingredient_in_hot_oven_progresses_through_states(
        self, world: World
    ) -> None:
        # Apple inside cake_tin on oven, oven HIGH (rate 0.06/s).
        tin = Container(id="tin_1", name="tin", in_id="oven")
        world.entities["tin_1"] = tin
        oven = world.entities["oven"]
        assert isinstance(oven, Appliance)
        oven.contents.append("tin_1")
        oven.setting = Setting.HIGH
        # Move apple into the tin.
        world.entities["fridge"].contents.remove("apple_1")  # type: ignore[union-attr]
        world.entities["apple_1"].in_id = "tin_1"
        tin.contents.append("apple_1")

        apple = world.entities["apple_1"]
        assert isinstance(apple, Ingredient)
        assert apple.cook_state == CookState.RAW

        # Rate 0.06/s — 6s progress=0.36 → COOKING
        ok, msg = wait(world, 6)
        assert ok, msg
        assert apple.cook_state == CookState.COOKING
        # 6s more → 0.72 still COOKING
        wait(world, 6)
        assert apple.cook_state == CookState.COOKING
        # 4s more → 0.96 → COOKED
        ok, msg = wait(world, 4)
        assert ok
        assert apple.cook_state == CookState.COOKED
        assert "cooked" in msg.lower()
        # 10s more → 1.56 → BURNT
        ok, msg = wait(world, 10)
        assert apple.cook_state == CookState.BURNT
        assert "burnt" in msg.lower()

    def test_off_appliance_does_not_cook(self, world: World) -> None:
        # Apple in fridge (setting OFF) — should not cook.
        wait(world, 30)
        apple = world.entities["apple_1"]
        assert isinstance(apple, Ingredient)
        assert apple.cook_state == CookState.RAW
        assert apple.cook_progress == 0.0
