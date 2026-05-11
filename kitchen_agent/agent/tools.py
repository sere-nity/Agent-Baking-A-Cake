"""Anthropic tool schemas — one per transition. Argument names match the
transition function parameter names exactly (see env/transitions.py)."""

from __future__ import annotations

from typing import Any

TOOLS: list[dict[str, Any]] = [
    {
        "name": "navigate_to",
        "description": (
            "Walk to a tile adjacent to the target entity. After arrival you "
            "will be facing it. Uses shortest-path BFS over the grid; walls "
            "and appliances block. Most other actions require you to be "
            "adjacent first, so this is usually the first step before any "
            "pick_up / place / pour / whisk / set_appliance on a remote "
            "target.\n\nPreconditions: target_id must exist in the world and "
            "have a fixed position (not currently held by you).\nExample: "
            "navigate_to(target_id='fridge')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "target_id": {
                    "type": "string",
                    "description": (
                        "Id of an appliance, container, or ingredient to walk near."
                    ),
                }
            },
            "required": ["target_id"],
        },
    },
    {
        "name": "pick_up",
        "description": (
            "Take an ingredient or container into one of your hands. You will "
            "use a free hand (left first).\n\nPreconditions: object_id is "
            "adjacent, at least one hand is free, object is not an appliance, "
            "and you are not already holding it.\nSide effects: object enters "
            "your hand; it is removed from its parent appliance/container's "
            "contents.\nExample: pick_up(object_id='egg_1')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "object_id": {
                    "type": "string",
                    "description": "Id of the ingredient or container to pick up.",
                }
            },
            "required": ["object_id"],
        },
    },
    {
        "name": "place",
        "description": (
            "Put a held item into/onto a target container or appliance. "
            "Ingredients can go into containers or appliances; containers can "
            "go onto appliances. Containers cannot be nested inside other "
            "containers.\n\nPreconditions: you are holding object_id, "
            "container_id is adjacent, container_id is not an ingredient.\n"
            "Side effects: object enters container.contents; the matching "
            "hand becomes free.\nExamples: place(object_id='egg_1', "
            "container_id='mixing_bowl'); place(object_id='cake_tin', "
            "container_id='oven')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "object_id": {
                    "type": "string",
                    "description": "Id of the held ingredient or container.",
                },
                "container_id": {
                    "type": "string",
                    "description": (
                        "Id of the receiving container or appliance "
                        "(despite the name, appliances are accepted)."
                    ),
                },
            },
            "required": ["object_id", "container_id"],
        },
    },
    {
        "name": "pour",
        "description": (
            "Pour every item from a held source container into an adjacent "
            "target. The source ends up empty.\n\nPreconditions: source_id "
            "is held by you and is a non-empty container; target_id is "
            "adjacent and is a container or appliance.\nSide effects: "
            "target.contents gains all of source's items; source.contents "
            "is cleared.\nExample: pour(source_id='mixing_bowl', "
            "target_id='cake_tin')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "Id of the held container to pour from.",
                },
                "target_id": {
                    "type": "string",
                    "description": "Id of the adjacent container/appliance to pour into.",
                },
            },
            "required": ["source_id", "target_id"],
        },
    },
    {
        "name": "whisk",
        "description": (
            "Whisk a container's contents. Always sets contents_whisked=True. "
            "If the container holds the full batter recipe (one of each: "
            "egg, flour, sugar, butter, milk), those ingredients are "
            "consumed and replaced by a single 'batter' ingredient inside "
            "the container.\n\nPreconditions: container_id is a container "
            "and is either held by you or adjacent.\nExample: "
            "whisk(container_id='mixing_bowl')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "Id of the container to whisk.",
                }
            },
            "required": ["container_id"],
        },
    },
    {
        "name": "set_appliance",
        "description": (
            "Change an adjacent appliance's setting. Valid settings: "
            "'off', 'low', 'medium', 'high'. Hot settings cook ingredients "
            "inside the appliance over time (use 'wait' to advance time).\n\n"
            "Preconditions: appliance_id is an adjacent appliance; setting "
            "is one of the four values.\nExample: set_appliance("
            "appliance_id='oven', setting='high')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "appliance_id": {
                    "type": "string",
                    "description": "Id of the adjacent appliance.",
                },
                "setting": {
                    "type": "string",
                    "enum": ["off", "low", "medium", "high"],
                    "description": "New setting for the appliance.",
                },
            },
            "required": ["appliance_id", "setting"],
        },
    },
    {
        "name": "wait",
        "description": (
            "Advance world time by N seconds. Ingredients inside any "
            "non-OFF appliance accumulate cook_progress and transition "
            "through RAW → COOKING → COOKED → BURNT. Use this only when "
            "you actually want time to pass (i.e. something is cooking) — "
            "otherwise it just wastes turns.\n\nPreconditions: seconds is "
            "a positive integer.\nExample: wait(seconds=10)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Number of seconds to advance.",
                }
            },
            "required": ["seconds"],
        },
    },
]
