"""Spritesheet rects and emoji mappings for the renderer.

SPRITES covers tiles + appliances (the only things on the spritesheet).
Containers and ingredients render as emoji instead — see EMOJI below."""

from __future__ import annotations

TILE_SIZE: int = 64

SPRITESHEET_PATH: str = "assets/kitchen_v1.png"

# Mapping: tile_kind or appliance_type -> (sx, sy, w, h) on the sheet.
SPRITES: dict[str, tuple[int, int, int, int]] = {
    # tiles
    "floor":          (288, 480, 32, 32),
    "wall":           (480, 448, 32, 32),
    # appliances
    "fridge":         (384, 192, 32, 64),  # 1x2 — rendered bottom-aligned
    "oven":           (512, 288, 32, 32),
    "counter":        (384, 64,  32, 64),
    "counter_corner": (480, 192, 32, 32),
    "counter_side":   (480, 224, 32, 32),
    "sink":           (384, 32,  32, 32),
    "microwave":      (128, 416, 32, 32),
    "toaster":        (96,  416, 32, 32),
}

# Foods → emoji. Used inside containers, in agent hands, and on appliances
# (when an ingredient sits directly inside an appliance like apple-in-fridge).
# Also keyed by container.name / container.container_type for containers,
# since they render as emoji rather than sprites.
EMOJI: dict[str, str] = {
    # ingredients (by `food`)
    "egg":    "🥚",
    "flour":  "🌾",
    "butter": "🧈",
    "milk":   "🥛",
    "sugar":  "🍬",
    "batter": "🥣",
    "cake":   "🍰",
    "apple":  "🍎",
    # containers (by `name` first)
    "mixing bowl": "🥣",
    "whisk":       "🥄",
    "cake tin":    "🎂",
    # containers (by `container_type` as fallback)
    "bowl": "🥣",
    "pan":  "🍳",
    "tin":  "🎂",
}
