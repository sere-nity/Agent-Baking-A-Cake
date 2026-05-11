"""Seven action transitions. Each mutates `world` in place and returns
(success, message). Error messages tell the agent what went wrong and
what to try next — they are the agent's primary recovery signal."""

from __future__ import annotations

from kitchen_agent.env.pathfinding import shortest_path
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

BATTER_RECIPE: frozenset[str] = frozenset(
    {"egg", "flour", "sugar", "butter", "milk"}
)

# cook_progress per second by setting.
_RATE_PER_SECOND: dict[Setting, float] = {
    Setting.OFF: 0.0,
    Setting.LOW: 0.02,
    Setting.MEDIUM: 0.04,
    Setting.HIGH: 0.06,
}


# ----- helpers ---------------------------------------------------------------


def _pos_str(p: Position) -> str:
    return f"({p.x},{p.y})"


def _name(world: World, entity_id: str) -> str:
    ent = world.entities.get(entity_id)
    return f"{ent.name} ({entity_id})" if ent is not None else f"'{entity_id}'"


def _is_held(world: World, entity_id: str) -> bool:
    return entity_id in (world.agent.left_hand, world.agent.right_hand)


def _is_adjacent(world: World, entity_id: str) -> bool:
    return any(e.id == entity_id for e in world.adjacent_entities())


def _ingredients_inside(
    world: World, root: Ingredient | Container | Appliance
) -> list[Ingredient]:
    if isinstance(root, Ingredient):
        return [root]
    out: list[Ingredient] = []
    for child_id in root.contents:
        child = world.entities.get(child_id)
        if child is None:
            continue
        out.extend(_ingredients_inside(world, child))
    return out


def _state_for_progress(p: float) -> CookState:
    if p < 0.3:
        return CookState.RAW
    if p < 0.8:
        return CookState.COOKING
    if p < 1.2:
        return CookState.COOKED
    return CookState.BURNT


def _facing_toward(from_pos: Position, to_pos: Position) -> Facing:
    if to_pos.x > from_pos.x:
        return Facing.EAST
    if to_pos.x < from_pos.x:
        return Facing.WEST
    if to_pos.y > from_pos.y:
        return Facing.SOUTH
    return Facing.NORTH


# ----- actions ---------------------------------------------------------------


def navigate_to(world: World, target_id: str) -> tuple[bool, str]:
    """Walk to a tile adjacent to the target entity."""
    target = world.entities.get(target_id)
    if target is None:
        return False, f"Cannot navigate: no entity with id '{target_id}'."

    if _is_held(world, target_id):
        return False, (
            f"Cannot navigate to {_name(world, target_id)}: you are holding it."
        )

    target_pos = world.entity_position(target_id)
    if target_pos is None:
        return False, (
            f"Cannot navigate to {_name(world, target_id)}: it has no fixed "
            "position in the world (not held, not in any appliance)."
        )

    if _is_adjacent(world, target_id):
        world.agent.facing = _facing_toward(world.agent.position, target_pos)
        return True, (
            f"Already adjacent to {_name(world, target_id)} at "
            f"{_pos_str(target_pos)}; now facing it."
        )

    path = shortest_path(world, world.agent.position, target_id)
    if path is None:
        return False, (
            f"Cannot navigate to {_name(world, target_id)} at "
            f"{_pos_str(target_pos)}: no walkable path."
        )

    destination = path[-1]
    world.agent.position = destination
    world.agent.facing = _facing_toward(destination, target_pos)
    return True, (
        f"Navigated to {_pos_str(destination)} adjacent to "
        f"{_name(world, target_id)} in {len(path) - 1} steps."
    )


def pick_up(world: World, object_id: str) -> tuple[bool, str]:
    """Pick up an ingredient or container from an adjacent appliance/container."""
    obj = world.entities.get(object_id)
    if obj is None:
        return False, f"Cannot pick up: no entity with id '{object_id}'."

    if isinstance(obj, Appliance):
        return False, (
            f"Cannot pick up {_name(world, object_id)}: appliances are fixed."
        )

    if _is_held(world, object_id):
        return False, f"Already holding {_name(world, object_id)}."

    if not _is_adjacent(world, object_id):
        obj_pos = world.entity_position(object_id)
        loc = (
            f" at {_pos_str(obj_pos)}" if obj_pos is not None else " (no position)"
        )
        return False, (
            f"Cannot pick up {_name(world, object_id)}: not adjacent. You are at "
            f"{_pos_str(world.agent.position)}; {object_id} is{loc}. "
            f"Try navigate_to('{object_id}') first."
        )

    if world.agent.hands_free == 0:
        return False, (
            f"Cannot pick up {_name(world, object_id)}: both hands full "
            f"(holding {world.agent.holding}). Place one item down first."
        )

    parent_id = obj.in_id
    if parent_id is not None:
        parent = world.entities.get(parent_id)
        if parent is not None and not isinstance(parent, Ingredient):
            if object_id in parent.contents:
                parent.contents.remove(object_id)

    obj.in_id = None
    if world.agent.left_hand is None:
        world.agent.left_hand = object_id
        hand = "left hand"
    else:
        world.agent.right_hand = object_id
        hand = "right hand"

    return True, f"Picked up {_name(world, object_id)} in {hand}."


def place(world: World, object_id: str, container_id: str) -> tuple[bool, str]:
    """Place a held ingredient or container into/onto a target.

    Ingredients can go into containers or appliances. Containers can go onto
    appliances. Containers cannot be nested inside other containers.
    """
    obj = world.entities.get(object_id)
    if obj is None:
        return False, f"Cannot place: no entity with id '{object_id}'."
    if not _is_held(world, object_id):
        return False, (
            f"Cannot place {_name(world, object_id)}: you are not holding it. "
            f"Pick it up first."
        )

    target = world.entities.get(container_id)
    if target is None:
        return False, f"Cannot place: no target entity with id '{container_id}'."
    if isinstance(target, Ingredient):
        return False, (
            f"Cannot place into {_name(world, container_id)}: it is an "
            f"ingredient and cannot hold items."
        )
    if isinstance(obj, Container) and isinstance(target, Container):
        return False, (
            f"Cannot place {_name(world, object_id)} into "
            f"{_name(world, container_id)}: containers cannot be nested."
        )
    if not _is_adjacent(world, container_id):
        return False, (
            f"Cannot place into {_name(world, container_id)}: not adjacent. "
            f"Try navigate_to('{container_id}') first."
        )

    if world.agent.left_hand == object_id:
        world.agent.left_hand = None
    else:
        world.agent.right_hand = None
    obj.in_id = container_id
    target.contents.append(object_id)

    return True, (
        f"Placed {_name(world, object_id)} into {_name(world, container_id)}."
    )


def pour(world: World, source_id: str, target_id: str) -> tuple[bool, str]:
    """Pour every ingredient from a held source container into an adjacent target."""
    source = world.entities.get(source_id)
    if source is None:
        return False, f"Cannot pour: no source entity with id '{source_id}'."
    if not isinstance(source, Container):
        return False, (
            f"Cannot pour from {_name(world, source_id)}: only containers can "
            f"be poured."
        )
    if not _is_held(world, source_id):
        return False, (
            f"Cannot pour from {_name(world, source_id)}: you must hold it. "
            f"Pick it up first."
        )
    if not source.contents:
        return False, f"Cannot pour from {_name(world, source_id)}: it is empty."

    target = world.entities.get(target_id)
    if target is None:
        return False, f"Cannot pour: no target entity with id '{target_id}'."
    if isinstance(target, Ingredient):
        return False, (
            f"Cannot pour into {_name(world, target_id)}: it is an ingredient."
        )
    if not _is_adjacent(world, target_id):
        return False, (
            f"Cannot pour into {_name(world, target_id)}: not adjacent. "
            f"Try navigate_to('{target_id}') first."
        )

    moved = list(source.contents)
    for child_id in moved:
        child = world.entities.get(child_id)
        if child is None:
            continue
        if not isinstance(child, Appliance):
            child.in_id = target_id
        target.contents.append(child_id)
    source.contents.clear()

    return True, (
        f"Poured {len(moved)} item(s) from {_name(world, source_id)} into "
        f"{_name(world, target_id)}."
    )


def whisk(world: World, container_id: str) -> tuple[bool, str]:
    """Whisk a container. Sets contents_whisked. If the full batter recipe
    (egg, flour, sugar, butter, milk) is inside, those ingredients are
    consumed and replaced by a single `batter` ingredient."""
    container = world.entities.get(container_id)
    if container is None:
        return False, f"Cannot whisk: no entity with id '{container_id}'."
    if not isinstance(container, Container):
        return False, (
            f"Cannot whisk {_name(world, container_id)}: only containers "
            f"can be whisked."
        )
    if not _is_held(world, container_id) and not _is_adjacent(world, container_id):
        return False, (
            f"Cannot whisk {_name(world, container_id)}: not adjacent and not "
            f"held. Pick it up or navigate to it."
        )

    container.contents_whisked = True

    foods: dict[str, list[str]] = {}
    for child_id in container.contents:
        child = world.entities.get(child_id)
        if isinstance(child, Ingredient):
            foods.setdefault(child.food, []).append(child_id)

    if not BATTER_RECIPE.issubset(foods.keys()):
        missing = sorted(BATTER_RECIPE - foods.keys())
        if missing:
            return True, (
                f"Whisked {_name(world, container_id)}. Not yet batter — "
                f"missing: {', '.join(missing)}."
            )
        return True, f"Whisked {_name(world, container_id)}."

    consumed: list[str] = []
    for food in BATTER_RECIPE:
        ing_id = foods[food][0]
        container.contents.remove(ing_id)
        del world.entities[ing_id]
        consumed.append(ing_id)

    batter_id = f"batter_{container_id}_{world.t}"
    while batter_id in world.entities:
        batter_id += "_x"
    batter = Ingredient(
        id=batter_id, food="batter", name="batter", in_id=container_id
    )
    world.entities[batter_id] = batter
    container.contents.append(batter_id)

    return True, (
        f"Whisked {_name(world, container_id)}. The contents combined into "
        f"batter ({batter_id})."
    )


def set_appliance(
    world: World, appliance_id: str, setting: str
) -> tuple[bool, str]:
    """Change an adjacent appliance's setting (off / low / medium / high)."""
    appl = world.entities.get(appliance_id)
    if appl is None:
        return False, f"Cannot set: no entity with id '{appliance_id}'."
    if not isinstance(appl, Appliance):
        return False, (
            f"Cannot set {_name(world, appliance_id)}: not an appliance."
        )
    if not _is_adjacent(world, appliance_id):
        return False, (
            f"Cannot set {_name(world, appliance_id)}: not adjacent. "
            f"Try navigate_to('{appliance_id}') first."
        )
    try:
        new_setting = Setting(setting)
    except ValueError:
        valid = ", ".join(s.value for s in Setting)
        return False, (
            f"Invalid setting '{setting}'. Choose one of: {valid}."
        )

    old_setting = appl.setting
    appl.setting = new_setting
    return True, (
        f"Set {_name(world, appliance_id)} from {old_setting.value} "
        f"to {new_setting.value}."
    )


def wait(world: World, seconds: int) -> tuple[bool, str]:
    """Advance world time. Ingredients inside any appliance whose setting is
    not OFF have their cook_progress advanced; thresholds promote them
    through RAW -> COOKING -> COOKED -> BURNT."""
    if not isinstance(seconds, int) or isinstance(seconds, bool):
        return False, f"Cannot wait: seconds must be an integer, got {seconds!r}."
    if seconds <= 0:
        return False, (
            f"Cannot wait {seconds} seconds: must be a positive integer."
        )

    world.t += seconds

    newly_cooked: list[str] = []
    newly_burnt: list[str] = []

    for appl in world.entities.values():
        if not isinstance(appl, Appliance):
            continue
        if appl.setting == Setting.OFF:
            continue
        rate = _RATE_PER_SECOND[appl.setting]
        for ing in _ingredients_inside(world, appl):
            ing.cook_progress += rate * seconds
            new_state = _state_for_progress(ing.cook_progress)
            if new_state != ing.cook_state:
                ing.cook_state = new_state
                if new_state == CookState.COOKED:
                    newly_cooked.append(_name(world, ing.id))
                elif new_state == CookState.BURNT:
                    newly_burnt.append(_name(world, ing.id))

    parts = [f"Waited {seconds}s (now t={world.t})."]
    if newly_cooked:
        parts.append(f"Cooked: {', '.join(newly_cooked)}.")
    if newly_burnt:
        parts.append(f"BURNT: {', '.join(newly_burnt)}.")
    return True, " ".join(parts)
