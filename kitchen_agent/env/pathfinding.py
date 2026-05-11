"""BFS over the grid. Used by navigate_to."""

from __future__ import annotations

from collections import deque

from kitchen_agent.world.schemas import Position, World

_DELTAS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def shortest_path(
    world: World, start: Position, target_id: str
) -> list[Position] | None:
    """Path from `start` to a walkable tile adjacent to the target entity.

    Returns the path including `start` as the first element and the
    destination as the last. Returns None if the target has no anchored
    position (e.g. it is being held), or if no walkable path exists.
    """
    target_pos = world.entity_position(target_id)
    if target_pos is None:
        return None

    goals: set[tuple[int, int]] = set()
    for dx, dy in _DELTAS:
        cand = Position(x=target_pos.x + dx, y=target_pos.y + dy)
        if not world.is_blocked(cand):
            goals.add((cand.x, cand.y))
    if not goals:
        return None

    if (start.x, start.y) in goals:
        return [start]

    visited: set[tuple[int, int]] = {(start.x, start.y)}
    queue: deque[tuple[Position, list[Position]]] = deque([(start, [start])])

    while queue:
        cur, path = queue.popleft()
        for dx, dy in _DELTAS:
            nx, ny = cur.x + dx, cur.y + dy
            if (nx, ny) in visited:
                continue
            cand = Position(x=nx, y=ny)
            if world.is_blocked(cand):
                continue
            visited.add((nx, ny))
            new_path = path + [cand]
            if (nx, ny) in goals:
                return new_path
            queue.append((cand, new_path))

    return None
