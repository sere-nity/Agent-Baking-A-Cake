from kitchen_agent.world.schemas import (
    ActionRecord,
    Agent,
    Appliance,
    Container,
    CookState,
    Facing,
    Ingredient,
    Position,
    Setting,
    World,
)


def test_position_frozen_and_hashable() -> None:
    p = Position(x=1, y=2)
    assert hash(p) == hash(Position(x=1, y=2))
    assert {p, Position(x=1, y=2)} == {p}


def test_cook_state_str_enum() -> None:
    assert CookState.RAW == "raw"
    assert CookState("cooked") is CookState.COOKED


def test_setting_str_enum() -> None:
    assert Setting.OFF == "off"
    assert Setting("high") is Setting.HIGH


def test_facing_default_is_south() -> None:
    a = Agent(position=Position(x=0, y=0))
    assert a.facing is Facing.SOUTH


def test_agent_hands_free_when_empty() -> None:
    a = Agent(position=Position(x=0, y=0))
    assert a.hands_free == 2
    assert a.holding == []


def test_agent_hands_free_one_held() -> None:
    a = Agent(position=Position(x=0, y=0), left_hand="apple_1")
    assert a.hands_free == 1
    assert a.holding == ["apple_1"]


def test_agent_hands_free_both_held() -> None:
    a = Agent(
        position=Position(x=0, y=0), left_hand="apple_1", right_hand="bowl_1"
    )
    assert a.hands_free == 0
    assert set(a.holding) == {"apple_1", "bowl_1"}


def _empty_world() -> World:
    return World(
        width=5,
        height=5,
        agent=Agent(position=Position(x=0, y=0)),
        goal="test",
    )


def test_world_get_returns_entity() -> None:
    apple = Ingredient(id="apple_1", name="apple")
    w = _empty_world()
    w.entities["apple_1"] = apple
    assert w.get("apple_1") is apple


def test_world_is_blocked_outside_grid() -> None:
    w = _empty_world()
    assert w.is_blocked(Position(x=-1, y=0))
    assert w.is_blocked(Position(x=5, y=0))
    assert w.is_blocked(Position(x=0, y=5))


def test_world_is_blocked_wall() -> None:
    w = _empty_world()
    w.walls.add((1, 1))
    assert w.is_blocked(Position(x=1, y=1))
    assert not w.is_blocked(Position(x=2, y=2))


def test_world_is_blocked_appliance_tile() -> None:
    w = _empty_world()
    w.entities["fridge"] = Appliance(
        id="fridge",
        name="fridge",
        position=Position(x=2, y=2),
        appliance_type="fridge",
    )
    assert w.is_blocked(Position(x=2, y=2))
    assert not w.is_blocked(Position(x=3, y=2))


def test_adjacent_entities_includes_appliance_and_contents() -> None:
    fridge = Appliance(
        id="fridge",
        name="fridge",
        position=Position(x=2, y=2),
        appliance_type="fridge",
        contents=["apple_1"],
    )
    apple = Ingredient(id="apple_1", name="apple", in_id="fridge")
    w = _empty_world()
    w.entities["fridge"] = fridge
    w.entities["apple_1"] = apple
    w.agent.position = Position(x=1, y=2)  # west of fridge
    adj_ids = {e.id for e in w.adjacent_entities()}
    assert {"fridge", "apple_1"} <= adj_ids


def test_adjacent_entities_excludes_far_things() -> None:
    fridge = Appliance(
        id="fridge",
        name="fridge",
        position=Position(x=4, y=4),
        appliance_type="fridge",
    )
    w = _empty_world()
    w.entities["fridge"] = fridge
    assert w.adjacent_entities() == []


def test_world_json_roundtrip_and_discriminator() -> None:
    fridge = Appliance(
        id="fridge",
        name="fridge",
        position=Position(x=2, y=2),
        appliance_type="fridge",
        contents=["apple_1"],
        setting=Setting.OFF,
    )
    apple = Ingredient(
        id="apple_1", name="apple", in_id="fridge", cook_state=CookState.RAW
    )
    bowl = Container(id="bowl_1", name="bowl", contents_whisked=False)
    w = World(
        width=10,
        height=8,
        walls={(0, 0), (0, 1)},
        entities={"fridge": fridge, "apple_1": apple, "bowl_1": bowl},
        agent=Agent(
            position=Position(x=3, y=3),
            left_hand="bowl_1",
            scratchpad=["plan: get apple"],
        ),
        t=5,
        goal="Bring me the apple.",
        history=[
            ActionRecord(
                t=1,
                action="pick_up",
                args={"object_id": "bowl_1"},
                success=True,
                message="ok",
            )
        ],
    )

    j = w.model_dump_json()
    w2 = World.model_validate_json(j)

    assert w2.width == 10
    assert w2.height == 8
    assert w2.walls == {(0, 0), (0, 1)}
    assert w2.t == 5
    assert w2.goal == "Bring me the apple."
    assert isinstance(w2.entities["fridge"], Appliance)
    assert isinstance(w2.entities["apple_1"], Ingredient)
    assert isinstance(w2.entities["bowl_1"], Container)
    assert w2.agent.left_hand == "bowl_1"
    assert w2.agent.hands_free == 1
    assert w2.agent.scratchpad == ["plan: get apple"]
    assert len(w2.history) == 1
    assert w2.history[0].action == "pick_up"


def test_discriminator_resolves_from_raw_dict() -> None:
    data = {
        "width": 3,
        "height": 3,
        "agent": {"position": {"x": 0, "y": 0}},
        "goal": "test",
        "entities": {
            "a": {"kind": "ingredient", "id": "a", "name": "apple"},
            "b": {"kind": "container", "id": "b", "name": "bowl"},
            "c": {
                "kind": "appliance",
                "id": "c",
                "name": "fridge",
                "position": {"x": 1, "y": 1},
                "appliance_type": "fridge",
            },
        },
    }
    w = World.model_validate(data)
    assert isinstance(w.entities["a"], Ingredient)
    assert isinstance(w.entities["b"], Container)
    assert isinstance(w.entities["c"], Appliance)


def test_action_record_fields() -> None:
    r = ActionRecord(
        t=1,
        action="pick_up",
        args={"object_id": "x"},
        success=False,
        message="not adjacent",
    )
    assert r.t == 1
    assert r.success is False
    assert r.message == "not adjacent"
    assert r.args == {"object_id": "x"}
