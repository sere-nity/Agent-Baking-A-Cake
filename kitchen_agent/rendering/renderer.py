"""Pygame renderer. Pure function of world state plus an optional speech
bubble (action verb + truncated thought, in the style of generative_agents).
Returns a pygame.Surface; callers convert to numpy with `render_world_array`.

Layout (top to bottom):
  - one tile of wall strip (so tall appliances like the fridge can extend up)
  - world.height tiles of playable area
  - goal strip
"""

from __future__ import annotations

import os
from pathlib import Path

# Headless-safe — must be set before importing pygame.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from kitchen_agent.rendering.sprites import (
    EMOJI,
    SPRITES,
    SPRITESHEET_PATH,
    TILE_SIZE,
)
from kitchen_agent.world.schemas import (
    Appliance,
    Container,
    Facing,
    Ingredient,
    World,
)

# ----- constants -------------------------------------------------------------

TOP_MARGIN_PX = TILE_SIZE  # one extra row above the world for the back wall

FLOOR_COLOUR = (220, 230, 240)
WALL_COLOUR = (90, 90, 100)
GRID_LINE_COLOUR = (200, 210, 220)
APPLIANCE_FALLBACK_COLOUR = (160, 170, 190)
CONTAINER_FALLBACK_COLOUR = (210, 195, 160)
AGENT_BODY_COLOUR = (240, 200, 120)
AGENT_FACING_COLOUR = (180, 70, 50)
BUBBLE_FILL = (255, 255, 240)
BUBBLE_BORDER = (60, 60, 60)
GOAL_STRIP_FILL = (40, 40, 50)
GOAL_STRIP_TEXT = (250, 250, 250)
LABEL_TEXT_COLOUR = (40, 40, 50)

GOAL_STRIP_HEIGHT = 36
BUBBLE_MAX_CHARS = 60
BUBBLE_PADDING = 6

# Appliance types that sit on top of a counter — draw a full counter sprite
# (32x64 in the sheet) underneath them.
APPLIANCES_ON_COUNTER: frozenset[str] = frozenset(
    {"microwave", "toaster", "sink"}
)

# Pixel offset upward for visual back-of-tile placement of 32x32 appliances.
APPLIANCE_Y_LIFT: dict[str, int] = {
    "microwave":      64,
    "toaster":        64,
    "sink":           64,
    "counter_corner": 64,
    "counter_side":   64,
    "oven":           64,
}


# ----- lazy resource loading -------------------------------------------------

_spritesheet: pygame.Surface | None = None
_emoji_font: pygame.font.Font | None = None
_text_font: pygame.font.Font | None = None
_small_font: pygame.font.Font | None = None


def _ensure_pygame() -> None:
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()


def _get_spritesheet() -> pygame.Surface | None:
    global _spritesheet
    if _spritesheet is not None:
        return _spritesheet
    path = Path(SPRITESHEET_PATH)
    if not path.exists():
        return None
    surf = pygame.image.load(str(path))
    try:
        _spritesheet = surf.convert_alpha()
    except pygame.error:
        _spritesheet = surf
    return _spritesheet


_APPLE_EMOJI_FONT_PATH = "/System/Library/Fonts/Apple Color Emoji.ttc"
# Apple Color Emoji is a bitmap font — only specific sizes are available.
# 137 is a known native strike; render there, then downscale with Lanczos.
_PIL_EMOJI_RENDER_SIZE = 137
_EMOJI_TARGET_PX = 36  # final pixel size of an emoji on the rendered tile

_pil_emoji_font: object | None = None
_emoji_surface_cache: dict[str, pygame.Surface | None] = {}


def _get_pil_emoji_font():
    global _pil_emoji_font
    if _pil_emoji_font is not None or not _PIL_AVAILABLE:
        return _pil_emoji_font
    if not os.path.exists(_APPLE_EMOJI_FONT_PATH):
        return None
    for sz in (_PIL_EMOJI_RENDER_SIZE, 109, 96, 64, 48):
        try:
            _pil_emoji_font = ImageFont.truetype(_APPLE_EMOJI_FONT_PATH, sz)
            return _pil_emoji_font
        except (OSError, IOError):
            continue
    return None


def _render_emoji_surface(emoji: str) -> pygame.Surface | None:
    """Render a colour emoji glyph to a pygame Surface via Pillow. Cached."""
    if emoji in _emoji_surface_cache:
        return _emoji_surface_cache[emoji]
    font = _get_pil_emoji_font()
    if font is None:
        _emoji_surface_cache[emoji] = None
        return None
    try:
        size = _PIL_EMOJI_RENDER_SIZE * 2
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((0, 0), emoji, embedded_color=True, font=font)
        bbox = canvas.getbbox()
        if bbox is None:
            _emoji_surface_cache[emoji] = None
            return None
        cropped = canvas.crop(bbox)
        # Scale to target size, preserving aspect.
        aspect = cropped.width / cropped.height
        new_h = _EMOJI_TARGET_PX
        new_w = max(1, int(round(new_h * aspect)))
        scaled = cropped.resize((new_w, new_h), Image.LANCZOS)
        surf = pygame.image.fromstring(scaled.tobytes(), scaled.size, "RGBA")
        try:
            surf = surf.convert_alpha()
        except pygame.error:
            pass
        _emoji_surface_cache[emoji] = surf
        return surf
    except Exception:
        _emoji_surface_cache[emoji] = None
        return None


def _get_emoji_font() -> pygame.font.Font:
    """Fallback only — used when PIL emoji rendering isn't available."""
    global _emoji_font
    if _emoji_font is None:
        _ensure_pygame()
        try:
            if os.path.exists(_APPLE_EMOJI_FONT_PATH):
                _emoji_font = pygame.font.Font(_APPLE_EMOJI_FONT_PATH, 32)
            else:
                _emoji_font = pygame.font.SysFont("Apple Color Emoji", 32)
        except Exception:
            _emoji_font = pygame.font.SysFont(None, 32)
    return _emoji_font


def _get_text_font() -> pygame.font.Font:
    global _text_font
    if _text_font is None:
        _ensure_pygame()
        _text_font = pygame.font.SysFont("Helvetica", 14)
    return _text_font


def _get_small_font() -> pygame.font.Font:
    global _small_font
    if _small_font is None:
        _ensure_pygame()
        _small_font = pygame.font.SysFont("Helvetica", 11)
    return _small_font


def _tile_px(x: int, y: int) -> tuple[int, int]:
    return (x * TILE_SIZE, y * TILE_SIZE + TOP_MARGIN_PX)


def _scaled_sprite(
    sheet: pygame.Surface, rect: tuple[int, int, int, int], w: int, h: int
) -> pygame.Surface:
    sx, sy, sw, sh = rect
    sub = sheet.subsurface(pygame.Rect(sx, sy, sw, sh))
    return pygame.transform.scale(sub, (w, h))


# ----- public API ------------------------------------------------------------


def render_world(
    world: World,
    current_action: str | None = None,
    current_thought: str | None = None,
) -> pygame.Surface:
    _ensure_pygame()
    sheet = _get_spritesheet()

    w_px = world.width * TILE_SIZE
    h_px = TOP_MARGIN_PX + world.height * TILE_SIZE + GOAL_STRIP_HEIGHT
    surface = pygame.Surface((w_px, h_px))
    surface.fill(FLOOR_COLOUR)

    _draw_top_wall_strip(surface, world, sheet)
    _draw_floor(surface, world, sheet)
    _draw_walls(surface, world, sheet)
    _draw_entities(surface, world, sheet)
    _draw_agent(surface, world)
    if current_action is not None:
        _draw_bubble(surface, world, current_action, current_thought)
    _draw_goal_strip(surface, world, w_px, h_px)
    return surface


def render_world_array(
    world: World,
    current_action: str | None = None,
    current_thought: str | None = None,
) -> np.ndarray:
    """Same as render_world but returns numpy uint8 (H, W, 3) for imageio."""
    surface = render_world(world, current_action, current_thought)
    pixels = pygame.surfarray.array3d(surface)  # (W, H, 3)
    return np.transpose(pixels, (1, 0, 2)).astype(np.uint8)


# ----- drawing primitives ----------------------------------------------------


def _draw_top_wall_strip(
    surface: pygame.Surface, world: World, sheet: pygame.Surface | None
) -> None:
    rect = SPRITES.get("wall", (0, 0, 0, 0))
    if sheet is not None and rect[2] > 0 and rect[3] > 0:
        tile = _scaled_sprite(sheet, rect, TILE_SIZE, TILE_SIZE)
        for x in range(world.width):
            surface.blit(tile, (x * TILE_SIZE, 0))
    else:
        pygame.draw.rect(surface, WALL_COLOUR, (0, 0, world.width * TILE_SIZE, TOP_MARGIN_PX))


def _draw_floor(
    surface: pygame.Surface, world: World, sheet: pygame.Surface | None
) -> None:
    rect = SPRITES.get("floor", (0, 0, 0, 0))
    if sheet is not None and rect[2] > 0 and rect[3] > 0:
        tile = _scaled_sprite(sheet, rect, TILE_SIZE, TILE_SIZE)
        for y in range(world.height):
            for x in range(world.width):
                px, py = _tile_px(x, y)
                surface.blit(tile, (px, py))
    else:
        for x in range(world.width + 1):
            pygame.draw.line(
                surface,
                GRID_LINE_COLOUR,
                (x * TILE_SIZE, TOP_MARGIN_PX),
                (x * TILE_SIZE, TOP_MARGIN_PX + world.height * TILE_SIZE),
            )
        for y in range(world.height + 1):
            pygame.draw.line(
                surface,
                GRID_LINE_COLOUR,
                (0, TOP_MARGIN_PX + y * TILE_SIZE),
                (world.width * TILE_SIZE, TOP_MARGIN_PX + y * TILE_SIZE),
            )


def _draw_walls(
    surface: pygame.Surface, world: World, sheet: pygame.Surface | None
) -> None:
    rect = SPRITES.get("wall", (0, 0, 0, 0))
    if sheet is not None and rect[2] > 0 and rect[3] > 0:
        tile = _scaled_sprite(sheet, rect, TILE_SIZE, TILE_SIZE)
        for (wx, wy) in world.walls:
            px, py = _tile_px(wx, wy)
            surface.blit(tile, (px, py))
    else:
        for (wx, wy) in world.walls:
            px, py = _tile_px(wx, wy)
            pygame.draw.rect(surface, WALL_COLOUR, (px, py, TILE_SIZE, TILE_SIZE))


def _draw_entities(
    surface: pygame.Surface, world: World, sheet: pygame.Surface | None
) -> None:
    for ent in world.entities.values():
        if not isinstance(ent, Appliance):
            continue
        _draw_appliance(surface, ent, sheet)
        for child_id in ent.contents:
            child = world.entities.get(child_id)
            if child is None:
                continue
            if isinstance(child, Container):
                _draw_container(surface, child, ent)
                ing_ids = [
                    cid
                    for cid in child.contents
                    if isinstance(world.entities.get(cid), Ingredient)
                ]
                if ing_ids:
                    first = world.entities[ing_ids[0]]
                    assert isinstance(first, Ingredient)
                    _draw_ingredient_in_container(surface, first, ent)
                    if len(ing_ids) > 1:
                        _draw_plus_marker(surface, ent, len(ing_ids) - 1)
            elif isinstance(child, Ingredient):
                _draw_ingredient_emoji(surface, child, ent)


def _draw_appliance(
    surface: pygame.Surface, app: Appliance, sheet: pygame.Surface | None
) -> None:
    px, py = _tile_px(app.position.x, app.position.y)
    rect = SPRITES.get(app.appliance_type, (0, 0, 0, 0))

    if sheet is None or rect[2] == 0 or rect[3] == 0:
        pygame.draw.rect(
            surface,
            APPLIANCE_FALLBACK_COLOUR,
            (px + 2, py + 2, TILE_SIZE - 4, TILE_SIZE - 4),
            border_radius=4,
        )
        _draw_label(surface, app.id, px, py)
        return

    # Counter base for appliances that visually sit on a counter.
    if app.appliance_type in APPLIANCES_ON_COUNTER:
        c_rect = SPRITES.get("counter", (0, 0, 0, 0))
        if c_rect[2] > 0 and c_rect[3] > 0:
            c_h = max(TILE_SIZE, int(round(TILE_SIZE * c_rect[3] / c_rect[2])))
            c_sprite = _scaled_sprite(sheet, c_rect, TILE_SIZE, c_h)
            surface.blit(c_sprite, (px, py + TILE_SIZE - c_h))

    sw, sh = rect[2], rect[3]
    target_w = TILE_SIZE
    target_h = max(TILE_SIZE, int(round(TILE_SIZE * sh / sw)))
    sprite = _scaled_sprite(sheet, rect, target_w, target_h)
    lift = APPLIANCE_Y_LIFT.get(app.appliance_type, 0)
    # Bottom-align (so 32x64 sprites extend up), then lift for back-of-tile feel.
    surface.blit(sprite, (px, py + TILE_SIZE - target_h - lift))


def _draw_container(
    surface: pygame.Surface,
    container: Container,
    on_appliance: Appliance,
) -> None:
    px, py = _tile_px(on_appliance.position.x, on_appliance.position.y)
    glyph = (
        EMOJI.get(container.name)
        or EMOJI.get(container.container_type)
        or f"[{container.container_type or container.name}]"
    )
    _draw_glyph(surface, glyph, px + TILE_SIZE // 2, py + TILE_SIZE // 2)


def _draw_ingredient_emoji(
    surface: pygame.Surface,
    ing: Ingredient,
    appliance: Appliance,
) -> None:
    px, py = _tile_px(appliance.position.x, appliance.position.y)
    text = EMOJI.get(ing.food, f"[{ing.food}]")
    _draw_glyph(surface, text, px + TILE_SIZE // 2, py + TILE_SIZE // 2)


def _draw_ingredient_in_container(
    surface: pygame.Surface,
    ing: Ingredient,
    appliance: Appliance,
) -> None:
    """Same tile as the container; offset down-right by ~12px so both are visible."""
    px, py = _tile_px(appliance.position.x, appliance.position.y)
    text = EMOJI.get(ing.food, f"[{ing.food}]")
    _draw_glyph(
        surface, text, px + TILE_SIZE // 2 + 12, py + TILE_SIZE // 2 + 12
    )


def _draw_plus_marker(
    surface: pygame.Surface, appliance: Appliance, extra_count: int
) -> None:
    """A small '+N' marker indicating there are more ingredients in the container."""
    px, py = _tile_px(appliance.position.x, appliance.position.y)
    font = _get_small_font()
    label = f"+{extra_count}"
    text_surf = font.render(label, True, LABEL_TEXT_COLOUR)
    surface.blit(text_surf, (px + TILE_SIZE - text_surf.get_width() - 4, py + 4))


def _draw_agent(surface: pygame.Surface, world: World) -> None:
    px, py = _tile_px(world.agent.position.x, world.agent.position.y)
    cx, cy = px + TILE_SIZE // 2, py + TILE_SIZE // 2
    pygame.draw.circle(surface, AGENT_BODY_COLOUR, (cx, cy), TILE_SIZE // 3)
    dx, dy = _facing_delta(world.agent.facing)
    end = (cx + dx * (TILE_SIZE // 3), cy + dy * (TILE_SIZE // 3))
    pygame.draw.line(surface, AGENT_FACING_COLOUR, (cx, cy), end, 4)

    held_glyphs: list[str] = []
    for hid in (world.agent.left_hand, world.agent.right_hand):
        if hid is None:
            continue
        ent = world.entities.get(hid)
        if isinstance(ent, Ingredient):
            held_glyphs.append(EMOJI.get(ent.food, f"[{ent.food}]"))
        elif isinstance(ent, Container):
            held_glyphs.append(f"[{ent.id[:6]}]")
    for i, glyph in enumerate(held_glyphs):
        _draw_glyph(surface, glyph, px + 14 + i * 24, py - 4)


def _draw_bubble(
    surface: pygame.Surface,
    world: World,
    action: str,
    thought: str | None,
) -> None:
    line = f"[{action}]"
    if thought:
        snippet = thought.strip().splitlines()[0][:BUBBLE_MAX_CHARS]
        if snippet:
            line = f"{line} {snippet}"
    font = _get_small_font()
    text_surf = font.render(line, True, LABEL_TEXT_COLOUR)
    tw, th = text_surf.get_size()

    ax_px, ay_px = _tile_px(world.agent.position.x, world.agent.position.y)
    cx = ax_px + TILE_SIZE // 2
    bw = tw + BUBBLE_PADDING * 2
    bh = th + BUBBLE_PADDING * 2
    bx = max(2, cx - bw // 2)
    by = max(2, ay_px - bh - 6)

    pygame.draw.rect(surface, BUBBLE_FILL, (bx, by, bw, bh), border_radius=6)
    pygame.draw.rect(surface, BUBBLE_BORDER, (bx, by, bw, bh), 1, border_radius=6)
    surface.blit(text_surf, (bx + BUBBLE_PADDING, by + BUBBLE_PADDING))


def _draw_goal_strip(
    surface: pygame.Surface, world: World, w_px: int, h_px: int
) -> None:
    strip_top = h_px - GOAL_STRIP_HEIGHT
    pygame.draw.rect(surface, GOAL_STRIP_FILL, (0, strip_top, w_px, GOAL_STRIP_HEIGHT))
    font = _get_text_font()
    line = f"t={world.t}  goal: {world.goal}"
    text_surf = font.render(line, True, GOAL_STRIP_TEXT)
    surface.blit(
        text_surf,
        (10, strip_top + (GOAL_STRIP_HEIGHT - text_surf.get_height()) // 2),
    )


# ----- helpers ---------------------------------------------------------------


def _draw_label(surface: pygame.Surface, label: str, px: int, py: int) -> None:
    font = _get_small_font()
    text_surf = font.render(label, True, LABEL_TEXT_COLOUR)
    surface.blit(text_surf, (px + 4, py + 4))


def _draw_glyph(surface: pygame.Surface, text: str, cx: int, cy: int) -> None:
    is_bracketed = text.startswith("[")
    if not is_bracketed:
        # Try PIL-based colour emoji rendering first — pygame/SDL_ttf draws
        # tofu for Apple Color Emoji because it doesn't read SBIX tables.
        emoji_surf = _render_emoji_surface(text)
        if emoji_surf is not None:
            gw, gh = emoji_surf.get_size()
            surface.blit(emoji_surf, (cx - gw // 2, cy - gh // 2))
            return
    font = _get_text_font() if is_bracketed else _get_emoji_font()
    try:
        glyph = font.render(text, True, LABEL_TEXT_COLOUR)
    except pygame.error:
        glyph = None
    if glyph is None or glyph.get_width() == 0:
        glyph = _get_text_font().render(
            text if is_bracketed else f"[{text}]", True, LABEL_TEXT_COLOUR
        )
    gw, gh = glyph.get_size()
    surface.blit(glyph, (cx - gw // 2, cy - gh // 2))


def _facing_delta(facing: Facing) -> tuple[int, int]:
    return {
        Facing.NORTH: (0, -1),
        Facing.SOUTH: (0, 1),
        Facing.EAST: (1, 0),
        Facing.WEST: (-1, 0),
    }[facing]
