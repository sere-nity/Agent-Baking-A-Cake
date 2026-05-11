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
from kitchen_agent.tasks import bake_cake, get_apple
from kitchen_agent.world.schemas import Facing, Position

TASKS = {"get_apple": get_apple, "bake_cake": bake_cake}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, choices=list(TASKS))
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--no-render", action="store_true")
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

    frames: list[Any] = []
    if not args.no_render:
        initial = env.render()
        if initial is not None:
            frames.append(initial)

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
        imageio.mimsave(str(gif_path), frames, duration=0.25, loop=0)
        console.print(f"[dim]gif: {gif_path}  ({len(frames)} frames)[/]")
    return 0 if final_done else 1


def _fmt_args(args: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def _frames_for_step(
    env: KitchenEnv,
    decision: AgentDecision,
    result: StepResult,
    pre_pos: Position,
) -> list[Any]:
    """One frame for most actions; one frame per traversed tile for navigate_to."""
    if decision.tool_name == "navigate_to" and result.success:
        target_id = decision.tool_args.get("target_id")
        path = shortest_path(env.world, pre_pos, str(target_id)) if target_id else None
        if path and len(path) > 1:
            final_pos = env.world.agent.position
            final_facing = env.world.agent.facing
            out: list[Any] = []
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
                    out.append(frame)
            env.world.agent.position = final_pos
            env.world.agent.facing = final_facing
            return out
    frame = env.render(
        current_action=decision.tool_name,
        current_thought=decision.reasoning or None,
    )
    return [frame] if frame is not None else []


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
