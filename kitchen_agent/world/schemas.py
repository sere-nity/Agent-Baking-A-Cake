"""World schemas. The world is the source of truth; only step() mutates."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, computed_field


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

    x: int
    y: int


class CookState(StrEnum):
    RAW = "raw"
    COOKING = "cooking"
    COOKED = "cooked"
    BURNT = "burnt"


class Setting(StrEnum):
    OFF = "off"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Facing(StrEnum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


_IN_ID_DESC = (
    "Id of the entity that contains or supports this one "
    "(e.g. apple's fridge, bowl's counter). None when the agent is holding it."
)
_CONTENTS_DESC = (
    "Ids of entities directly contained or supported by this one "
    "(e.g. ingredients in a bowl, containers on a counter)."
)


class Ingredient(BaseModel):
    kind: Literal["ingredient"] = "ingredient"
    id: str
    food: str = Field(
        description=(
            "Stable kind identifier (e.g. 'egg', 'flour', 'batter'). "
            "Used for recipe matching, emoji lookup, and goal checks. "
            "Independent of `name`, which is the display string."
        )
    )
    name: str = Field(description="Human-readable display name.")
    in_id: str | None = Field(default=None, description=_IN_ID_DESC)
    cook_state: CookState = CookState.RAW
    cook_progress: float = 0.0


class Container(BaseModel):
    kind: Literal["container"] = "container"
    id: str
    name: str
    in_id: str | None = Field(default=None, description=_IN_ID_DESC)
    contents: list[str] = Field(default_factory=list, description=_CONTENTS_DESC)
    contents_whisked: bool = False


class Appliance(BaseModel):
    kind: Literal["appliance"] = "appliance"
    id: str
    name: str
    position: Position
    appliance_type: str
    setting: Setting = Setting.OFF
    contents: list[str] = Field(default_factory=list, description=_CONTENTS_DESC)


Entity = Annotated[
    Union[Ingredient, Container, Appliance],
    Field(discriminator="kind"),
]


class Agent(BaseModel):
    position: Position
    facing: Facing = Facing.SOUTH
    left_hand: str | None = None
    right_hand: str | None = None
    scratchpad: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def hands_free(self) -> int:
        return int(self.left_hand is None) + int(self.right_hand is None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def holding(self) -> list[str]:
        return [h for h in (self.left_hand, self.right_hand) if h is not None]


class ActionRecord(BaseModel):
    t: int
    action: str
    args: dict[str, Any] = Field(default_factory=dict)
    success: bool
    message: str


class World(BaseModel):
    width: int
    height: int
    walls: set[tuple[int, int]] = Field(default_factory=set)
    entities: dict[str, Entity] = Field(default_factory=dict)
    agent: Agent
    t: int = 0
    goal: str
    history: list[ActionRecord] = Field(default_factory=list)

    def get(self, entity_id: str) -> Ingredient | Container | Appliance:
        return self.entities[entity_id]

    def is_blocked(self, pos: Position) -> bool:
        if pos.x < 0 or pos.x >= self.width or pos.y < 0 or pos.y >= self.height:
            return True
        if (pos.x, pos.y) in self.walls:
            return True
        for ent in self.entities.values():
            if isinstance(ent, Appliance) and ent.position == pos:
                return True
        return False

    def adjacent_entities(self) -> list[Ingredient | Container | Appliance]:
        ax, ay = self.agent.position.x, self.agent.position.y
        neighbours = {(ax + 1, ay), (ax - 1, ay), (ax, ay + 1), (ax, ay - 1)}
        result: list[Ingredient | Container | Appliance] = []
        for ent in self.entities.values():
            pos = self._effective_position(ent)
            if pos is None:
                continue
            if (pos.x, pos.y) in neighbours:
                result.append(ent)
                result.extend(self._descendants(ent))
        return result

    def _effective_position(
        self, ent: Ingredient | Container | Appliance
    ) -> Position | None:
        if isinstance(ent, Appliance):
            return ent.position
        parent_id = ent.in_id
        if parent_id is None:
            return None
        parent = self.entities.get(parent_id)
        if parent is None:
            return None
        return self._effective_position(parent)

    def _descendants(
        self, ent: Ingredient | Container | Appliance
    ) -> list[Ingredient | Container | Appliance]:
        if isinstance(ent, Ingredient):
            return []
        out: list[Ingredient | Container | Appliance] = []
        for child_id in ent.contents:
            child = self.entities.get(child_id)
            if child is None:
                continue
            out.append(child)
            out.extend(self._descendants(child))
        return out
