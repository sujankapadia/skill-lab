"""Extract behavioral evidence from a Harbor ATIF trajectory.

Deliberately shallow (§11): enough for the summarizer to describe what a run
did, not a full trace model. Claude Code tool names are used as-is.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from skill_lab.models.run_record import ToolCall

# Which argument best identifies a call, per Claude Code tool.
_KEY_ARG = {
    "Bash": "command",
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
    "Glob": "pattern",
    "Grep": "pattern",
    "Skill": "skill",
    "Agent": "description",
    "WebFetch": "url",
    "WebSearch": "query",
}


@dataclass
class TrajectoryFacts:
    schema_version: str | None
    agent_name: str | None
    agent_version: str | None
    model: str | None
    n_steps: int
    tool_calls: list[ToolCall] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    final_response: str | None = None
    final_metrics: dict = field(default_factory=dict)


def message_text(message) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        return "\n".join(
            p.get("text", "") for p in message if isinstance(p, dict) and p.get("type") == "text"
        )
    return ""


def summarize_call(name: str, arguments: dict | None) -> str:
    arguments = arguments or {}
    key = _KEY_ARG.get(name)
    if key and key in arguments:
        value = str(arguments[key])
    elif arguments:
        value = json.dumps(arguments, sort_keys=True)
    else:
        value = ""
    value = " ".join(value.split())
    return value[:200] + ("…" if len(value) > 200 else "")


def parse_trajectory(path: Path) -> TrajectoryFacts:
    traj = json.loads(path.read_text())
    agent = traj.get("agent") or {}
    facts = TrajectoryFacts(
        schema_version=traj.get("schema_version"),
        agent_name=agent.get("name"),
        agent_version=agent.get("version"),
        model=agent.get("model_name"),
        n_steps=len(traj.get("steps", [])),
        final_metrics=traj.get("final_metrics") or {},
    )
    for step in traj.get("steps", []):
        if step.get("source") != "agent":
            continue
        for call in step.get("tool_calls") or []:
            name = call.get("function_name") or "?"
            args = call.get("arguments") or {}
            facts.tool_calls.append(ToolCall(step["step_id"], name, summarize_call(name, args)))
            if name == "Bash" and args.get("command"):
                facts.commands.append(args["command"])
        text = message_text(step.get("message")).strip()
        if text:
            facts.final_response = text
    return facts
