"""Build the per-turn observation. Pure: a function of world state only.

Four markdown sections in this order:
  ## Right now    position, facing, hands, adjacent entities (second-person)
  ## Kitchen      every appliance, its setting, and what's in/on it
  ## Goal + Notes goal string and the agent's scratchpad
  ## Recent       last 3 history entries with ✓/✗

Static info (action semantics, persona, rules) belongs in the system prompt,
not here. This text is rebuilt every turn — keep it tight.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kitchen_agent.world.schemas import (
    ActionRecord,
    Appliance,
    Container,
    CookState,
    Ingredient,
    Setting,
    World,
)


@dataclass
class Observation:
    text: str
    available_actions: list[dict[str, Any]] = field(default_factory=list)


def build_observation(world: World) -> Observation:
    text = "\n\n".join(
        [
            _section_right_now(world),
            _section_kitchen(world),
            _section_goal_notes(world),
            _section_recent(world),
        ]
    )
    return Observation(text=text)


# ----- sections --------------------------------------------------------------


def _section_right_now(world: World) -> str:
    p = world.agent.position
    facing = world.agent.facing.value
    return "\n".join(
        [
            "## Right now",
            f"- You are at ({p.x},{p.y}), facing {facing}.",
            f"- Hands: {_hands_str(world)}.",
            f"- Adjacent: {_adjacent_str(world)}.",
        ]
    )


def _section_kitchen(world: World) -> str:
    lines = ["## Kitchen"]
    for ent in world.entities.values():
        if not isinstance(ent, Appliance):
            continue
        head = f"- {ent.id} at ({ent.position.x},{ent.position.y})"
        if ent.setting != Setting.OFF:
            head += f" [{ent.setting.value}]"
        if not ent.contents:
            lines.append(f"{head}: empty")
        else:
            inside = ", ".join(_describe_in_kitchen(world, c) for c in ent.contents)
            lines.append(f"{head}: {inside}")
    return "\n".join(lines)


def _section_goal_notes(world: World) -> str:
    lines = ["## Goal + Notes", f"- Goal: {world.goal}"]
    if world.agent.scratchpad:
        for note in world.agent.scratchpad:
            lines.append(f"- Note: {note}")
    else:
        lines.append("- Scratchpad: (empty)")
    return "\n".join(lines)


def _section_recent(world: World) -> str:
    lines = ["## Recent"]
    if not world.history:
        lines.append("- (no actions yet)")
        return "\n".join(lines)
    for record in world.history[-3:]:
        lines.append(f"- {_format_record(record)}")
    return "\n".join(lines)


# ----- helpers ---------------------------------------------------------------


def _hands_str(world: World) -> str:
    parts = []
    for label, hid in (
        ("left", world.agent.left_hand),
        ("right", world.agent.right_hand),
    ):
        if hid is None:
            parts.append(f"{label}=empty")
            continue
        held = world.entities.get(hid)
        if isinstance(held, Container) and held.contents:
            inner = ", ".join(_describe_brief(world, c) for c in held.contents)
            parts.append(f"{label}={hid} ⟨{inner}⟩")
        else:
            parts.append(f"{label}={hid}")
    return ", ".join(parts)


def _adjacent_str(world: World) -> str:
    ax, ay = world.agent.position.x, world.agent.position.y
    neighbours = {(ax + 1, ay), (ax - 1, ay), (ax, ay + 1), (ax, ay - 1)}
    appliances = [
        e
        for e in world.entities.values()
        if isinstance(e, Appliance) and (e.position.x, e.position.y) in neighbours
    ]
    if not appliances:
        return "nothing within reach"
    parts = []
    for app in appliances:
        if app.contents:
            inner = ", ".join(_describe_brief(world, c) for c in app.contents)
            parts.append(f"{app.id} ({inner})")
        else:
            parts.append(f"{app.id} (empty)")
    return "; ".join(parts)


def _describe_brief(world: World, entity_id: str) -> str:
    """Compact form for nested/adjacent lists. Id only, plus [state] / [whisked]."""
    ent = world.entities.get(entity_id)
    if ent is None:
        return entity_id
    if isinstance(ent, Ingredient):
        if ent.cook_state != CookState.RAW:
            return f"{entity_id} [{ent.cook_state.value}]"
        return entity_id
    if isinstance(ent, Container):
        return f"{entity_id}{' [whisked]' if ent.contents_whisked else ''}"
    return entity_id


def _describe_in_kitchen(world: World, entity_id: str) -> str:
    """Kitchen-section form: expand container contents one level deep."""
    ent = world.entities.get(entity_id)
    if ent is None:
        return entity_id
    if isinstance(ent, Ingredient):
        if ent.cook_state != CookState.RAW:
            return f"{entity_id} [{ent.cook_state.value}]"
        return entity_id
    if isinstance(ent, Container):
        head = entity_id
        if ent.contents_whisked:
            head += " [whisked]"
        if ent.contents:
            inner = ", ".join(_describe_brief(world, c) for c in ent.contents)
            return f"{head} ⟨{inner}⟩"
        return head
    return entity_id


def _format_record(r: ActionRecord) -> str:
    mark = "✓" if r.success else "✗"
    args = ", ".join(str(v) for v in r.args.values())
    return f"{mark} {r.action}({args}) — {r.message}"
