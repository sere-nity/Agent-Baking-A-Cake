"""CLI entry: drive the env with a Claude agent and log every turn."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path
from typing import Any

import anthropic
import imageio.v2 as imageio
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from kitchen_agent.agent.claude_agent import SYSTEM_PROMPT, ClaudeAgent, AgentDecision
from kitchen_agent.agent.tools import TOOLS
from kitchen_agent.env.environment import KitchenEnv, StepResult
from kitchen_agent.env.pathfinding import shortest_path
from kitchen_agent.env.transitions import (
    _RATE_PER_SECOND,
    _ingredients_inside,
    _state_for_progress,
)
from kitchen_agent.tasks import bake_cake, get_apple
from kitchen_agent.world.schemas import Appliance, Facing, Position, Setting

TASKS = {"get_apple": get_apple, "bake_cake": bake_cake}

# Per-category GIF frame durations (milliseconds).
WALK_FRAME_MS = 180     # navigate_to: fast tile-by-tile movement
WAIT_FRAME_MS = 600     # wait: dwell on each meaningful state change
ACTION_FRAME_MS = 700   # everything else: leave time to read what changed
DWELL_FRAME_MS = 900    # extra "look at the cake" frames after goal met


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, choices=list(TASKS))
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument(
        "--gif-end-pause-seconds",
        type=float,
        default=3.0,
        help="Extra dwell time on the final frame before the GIF loops (default 3s).",
    )
    args = parser.parse_args()

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY not set. Add it to .env or export it.",
            file=sys.stderr,
        )
        return 2

    console = Console()
    task = TASKS[args.task]
    env = KitchenEnv(task)
    obs = env.reset()

    client = anthropic.Anthropic()
    agent = ClaudeAgent(client, TOOLS, SYSTEM_PROMPT, model=args.model)

    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = Path("outputs") / f"run_{args.task}_{ts}.jsonl"
    gif_path = Path("outputs") / f"run_{args.task}_{ts}.gif"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    console.rule(f"[bold]{args.task}[/]  (model={args.model}, max_steps={args.max_steps})")
    console.print(Panel(obs.text, title="initial observation", border_style="cyan"))

    frames: list[tuple[Any, int]] = []
    if not args.no_render:
        initial = env.render()
        if initial is not None:
            frames.append((initial, ACTION_FRAME_MS))

    final_done = False
    with log_path.open("w") as log_file:
        for step_no in range(1, args.max_steps + 1):
            decision = agent.act(obs)

            if decision.reasoning:
                console.print(
                    Panel(
                        decision.reasoning,
                        title=f"thinking · turn {step_no}",
                        border_style="dim",
                    )
                )
            console.print(
                f"[bold yellow]→ {decision.tool_name}({_fmt_args(decision.tool_args)})[/]"
            )

            pre_pos = env.world.agent.position

            result = env.step(decision.tool_name, decision.tool_args)
            agent.record_step_result(result.success, result.message)

            if not args.no_render:
                frames.extend(_frames_for_step(env, decision, result, pre_pos))

            mark = "✓" if result.success else "✗"
            colour = "green" if result.success else "red"
            console.print(f"  [{colour}]{mark}[/] {result.message}")
            console.print(
                Panel(
                    result.observation.text,
                    title=f"obs · t={env.world.t}",
                    border_style="cyan",
                )
            )

            log_file.write(
                json.dumps(
                    {
                        "step": step_no,
                        "t": env.world.t,
                        "tool_name": decision.tool_name,
                        "tool_args": decision.tool_args,
                        "success": result.success,
                        "message": result.message,
                        "reasoning": decision.reasoning,
                        "done": result.done,
                    }
                )
                + "\n"
            )
            log_file.flush()

            obs = result.observation
            if result.done:
                final_done = True
                console.rule(f"[bold green]GOAL MET at step {step_no}[/]")
                break
        else:
            console.rule("[bold red]step limit reached[/]")

    console.print(f"[dim]log: {log_path}[/]")
    if frames and not args.no_render:
        # When the goal was met, append a few "look at the cake" dwell frames
        # of the final state so the success is obvious before the loop.
        if final_done:
            last_frame, _ = frames[-1]
            for _ in range(3):
                frames.append((last_frame, DWELL_FRAME_MS))
        # Extend the very last frame's duration with the end-pause.
        end_pause_ms = int(round(args.gif_end_pause_seconds * 1000))
        last_frame, last_ms = frames[-1]
        frames[-1] = (last_frame, max(last_ms, end_pause_ms))

        imgs = [f for f, _ in frames]
        durations = [ms for _, ms in frames]
        imageio.mimsave(str(gif_path), imgs, duration=durations, loop=0)
        console.print(
            f"[dim]gif: {gif_path}  ({len(imgs)} frames, end pause "
            f"{args.gif_end_pause_seconds:.1f}s)[/]"
        )
    return 0 if final_done else 1


def _fmt_args(args: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def _frames_for_step(
    env: KitchenEnv,
    decision: AgentDecision,
    result: StepResult,
    pre_pos: Position,
) -> list[tuple[Any, int]]:
    """Returns (frame, duration_ms) tuples per step.
    - navigate_to: one frame per traversed tile, fast
    - wait: only emit on cook-state changes + final frame, medium
    - other: one slow frame
    """
    if decision.tool_name == "navigate_to" and result.success:
        target_id = decision.tool_args.get("target_id")
        path = shortest_path(env.world, pre_pos, str(target_id)) if target_id else None
        if path and len(path) > 1:
            final_pos = env.world.agent.position
            final_facing = env.world.agent.facing
            out: list[tuple[Any, int]] = []
            for i in range(1, len(path)):
                env.world.agent.position = path[i]
                env.world.agent.facing = (
                    _face_toward(path[i], path[i + 1])
                    if i < len(path) - 1
                    else final_facing
                )
                frame = env.render(
                    current_action=decision.tool_name,
                    current_thought=decision.reasoning or None,
                )
                if frame is not None:
                    out.append((frame, WALK_FRAME_MS))
            env.world.agent.position = final_pos
            env.world.agent.facing = final_facing
            return out

    if decision.tool_name == "wait" and result.success:
        seconds = int(decision.tool_args.get("seconds", 0) or 0)
        if seconds > 0:
            return _wait_animation_frames(env, decision, seconds)

    frame = env.render(
        current_action=decision.tool_name,
        current_thought=decision.reasoning or None,
    )
    return [(frame, ACTION_FRAME_MS)] if frame is not None else []


def _wait_animation_frames(
    env: KitchenEnv, decision: AgentDecision, seconds: int
) -> list[tuple[Any, int]]:
    """Rewind the wait, then step one second at a time. Emit a frame ONLY
    when an ingredient's cook_state changes, plus a final frame. End state
    matches what env.step produced."""
    world = env.world

    world.t -= seconds
    cooking_pairs: list[tuple[Appliance, float]] = []
    for ent in world.entities.values():
        if isinstance(ent, Appliance) and ent.setting != Setting.OFF:
            cooking_pairs.append((ent, _RATE_PER_SECOND[ent.setting]))
    for appl, rate in cooking_pairs:
        for ing in _ingredients_inside(world, appl):
            ing.cook_progress = max(0.0, ing.cook_progress - rate * seconds)
            ing.cook_state = _state_for_progress(ing.cook_progress)

    def _state_snapshot() -> dict[str, str]:
        snap: dict[str, str] = {}
        for appl, _r in cooking_pairs:
            for ing in _ingredients_inside(world, appl):
                snap[ing.id] = ing.cook_state.value
        return snap

    out: list[tuple[Any, int]] = []
    last_states = _state_snapshot()
    for s in range(seconds):
        world.t += 1
        for appl, rate in cooking_pairs:
            for ing in _ingredients_inside(world, appl):
                ing.cook_progress += rate
                ing.cook_state = _state_for_progress(ing.cook_progress)
        cur_states = _state_snapshot()
        is_final_second = (s == seconds - 1)
        any_change = any(cur_states[k] != last_states.get(k) for k in cur_states)
        if any_change or is_final_second:
            frame = env.render(
                current_action=decision.tool_name,
                current_thought=decision.reasoning or None,
            )
            if frame is not None:
                out.append((frame, WAIT_FRAME_MS))
        last_states = cur_states
    return out


def _face_toward(src: Position, dst: Position) -> Facing:
    if dst.x > src.x:
        return Facing.EAST
    if dst.x < src.x:
        return Facing.WEST
    if dst.y > src.y:
        return Facing.SOUTH
    return Facing.NORTH


if __name__ == "__main__":
    sys.exit(main())
