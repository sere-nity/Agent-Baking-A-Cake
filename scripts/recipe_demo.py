"""Hand-driven walk-through of the cake recipe. No LLM.
Exercises the env to prove the seven transitions compose correctly."""

from __future__ import annotations

from kitchen_agent.env.environment import KitchenEnv
from kitchen_agent.tasks import bake_cake
from kitchen_agent.world.schemas import Appliance, Container, Ingredient


def snapshot(env: KitchenEnv) -> str:
    w = env.world
    a = w.agent
    bowl = w.entities.get("mixing_bowl")
    tin = w.entities.get("cake_tin")
    oven = w.entities.get("oven")
    assert isinstance(bowl, Container) and isinstance(tin, Container) and isinstance(oven, Appliance)

    batter_progress = "—"
    for cid in tin.contents:
        ing = w.entities.get(cid)
        if isinstance(ing, Ingredient) and ing.food == "batter":
            batter_progress = f"{ing.cook_progress:.2f} ({ing.cook_state.value})"
            break
        if isinstance(ing, Ingredient):
            batter_progress = f"{ing.food}:{ing.cook_progress:.2f} ({ing.cook_state.value})"

    return (
        f"t={w.t} pos=({a.position.x},{a.position.y}) face={a.facing.value} "
        f"L={a.left_hand} R={a.right_hand} "
        f"bowl={bowl.contents} tin={tin.contents} "
        f"oven={oven.setting.value} batter={batter_progress}"
    )


def step(env: KitchenEnv, n: int, label: str, action: str, **args) -> None:
    r = env.step(action, args)
    flag = "OK " if r.success else "FAIL"
    print(f"  [{n:2d}] {flag} {action}({args}) — {label}")
    print(f"        msg:  {r.message}")
    print(f"        state {snapshot(env)}")
    if not r.success:
        print(f"        !! recipe halted at step {n}")
        raise SystemExit(1)


def main() -> None:
    env = KitchenEnv(bake_cake)
    obs = env.reset()
    print("RESET")
    print(f"  goal: {env.world.goal}")
    print(f"  state: {snapshot(env)}")
    print()

    n = 0

    # --- Gather ingredients into the mixing bowl on counter_2 -----------------
    for ing_id, source_id in [
        ("egg_1", "fridge"),
        ("butter_1", "fridge"),
        ("milk_1", "fridge"),
        ("flour_1", "counter_3"),
        ("sugar_1", "counter_3"),
    ]:
        n += 1; step(env, n, f"go to {source_id}", "navigate_to", target_id=source_id)
        n += 1; step(env, n, f"pick {ing_id}", "pick_up", object_id=ing_id)
        n += 1; step(env, n, "go to mixing_bowl", "navigate_to", target_id="counter_2")
        n += 1; step(env, n, f"drop {ing_id} into bowl", "place", object_id=ing_id, container_id="mixing_bowl")

    # --- Whisk the bowl (creates batter) -------------------------------------
    n += 1; step(env, n, "whisk the bowl", "whisk", container_id="mixing_bowl")

    # --- Transfer batter from bowl to tin ------------------------------------
    n += 1; step(env, n, "pick up the (now-whisked) bowl", "pick_up", object_id="mixing_bowl")
    n += 1; step(env, n, "pour batter into tin", "pour", source_id="mixing_bowl", target_id="cake_tin")
    n += 1; step(env, n, "place empty bowl back on counter", "place", object_id="mixing_bowl", container_id="counter_2")

    # --- Move tin to oven and cook --------------------------------------------
    n += 1; step(env, n, "pick up the cake tin", "pick_up", object_id="cake_tin")
    n += 1; step(env, n, "walk to the oven", "navigate_to", target_id="oven")
    n += 1; step(env, n, "place tin in oven", "place", object_id="cake_tin", container_id="oven")
    n += 1; step(env, n, "turn oven on high", "set_appliance", appliance_id="oven", setting="high")

    # --- Wait for the batter to cook (rate 0.06/s, COOKED at 0.8..1.2) -------
    for i in range(1, 4):
        n += 1; step(env, n, f"wait #{i}", "wait", seconds=5)
        if env.is_goal_met():
            break

    print()
    print(f"DONE  steps={n}  goal_met={env.is_goal_met()}")


if __name__ == "__main__":
    main()
