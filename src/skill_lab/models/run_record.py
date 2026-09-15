"""Normalized view of one Harbor trial.

Kept deliberately small (§9 of the plan): fields are added only when a real
experiment demonstrates a need.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ToolCall:
    step_id: int
    name: str
    # Compact one-line rendering of the arguments (a Bash command, a file
    # path, ...). The full arguments stay in the trajectory.
    summary: str


@dataclass
class DiffStats:
    files_changed: int
    insertions: int
    deletions: int


@dataclass
class RunRecord:
    experiment_id: str
    run_id: str

    completed: bool
    error: str | None

    final_response: str | None

    started_at: str | None
    duration_seconds: float | None
    input_tokens: int | None
    cache_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None

    tool_calls: list[ToolCall] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)

    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)

    diff_patch_path: str | None = None
    diff_stats: DiffStats | None = None

    harbor_trial_name: str | None = None
    harbor_trial_path: str = ""
    trajectory_path: str | None = None
    workspace_path: str | None = None

    agent_name: str | None = None
    agent_version: str | None = None
    model: str | None = None

    # Interactive (simulated-user) runs.
    interactive: bool = False
    user_trajectory_path: str | None = None
    user_turns: int = 0            # messages the simulated user sent
    awaiting_input: bool = False   # the agent's last message was a question nobody answered

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RunRecord":
        data = dict(data)
        data["tool_calls"] = [ToolCall(**tc) for tc in data.get("tool_calls", [])]
        if data.get("diff_stats") is not None:
            data["diff_stats"] = DiffStats(**data["diff_stats"])
        return cls(**data)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "RunRecord":
        return cls.from_dict(json.loads(path.read_text()))
