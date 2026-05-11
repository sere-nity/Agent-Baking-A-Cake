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
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from kitchen_agent.agent.claude_agent import SYSTEM_PROMPT, ClaudeAgent
from kitchen_agent.agent.tools import TOOLS
from kitchen_agent.env.environment import KitchenEnv
from kitchen_agent.tasks import bake_cake, get_apple

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
    log_path.parent.mkdir(parents=True, exist_ok=True)

    console.rule(f"[bold]{args.task}[/]  (model={args.model}, max_steps={args.max_steps})")
    console.print(Panel(obs.text, title="initial observation", border_style="cyan"))

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

            result = env.step(decision.tool_name, decision.tool_args)
            agent.record_step_result(result.success, result.message)

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
    return 0 if final_done else 1


def _fmt_args(args: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


if __name__ == "__main__":
    sys.exit(main())
