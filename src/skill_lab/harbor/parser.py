"""Read a Harbor job directory and normalize each trial into a RunRecord.

This is the only module that knows Harbor's on-disk layout (documented in
docs/harbor-spike.md). The rest of Skill Lab works with RunRecords.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from skill_lab.harbor.trajectory import parse_trajectory
from skill_lab.models.run_record import RunRecord
from skill_lab.workspace.git_diff import WorkspaceChanges, workspace_changes

WORKSPACE_ARTIFACT = "app"  # mirrors the container's /app


@dataclass
class HarborTrial:
    path: Path
    result: dict

    @property
    def name(self) -> str:
        return self.result.get("trial_name") or self.path.name

    @property
    def started_at(self) -> str | None:
        return self.result.get("started_at")

    @property
    def trajectory_path(self) -> Path | None:
        p = self.path / "agent" / "trajectory.json"
        return p if p.exists() else None

    @property
    def workspace_path(self) -> Path | None:
        p = self.path / "artifacts" / WORKSPACE_ARTIFACT
        return p if (p / ".git").exists() else None

    @property
    def skill_digest(self) -> str | None:
        lock = self.path / "lock.json"
        if not lock.exists():
            return None
        skills = json.loads(lock.read_text()).get("skills") or []
        return skills[0].get("digest") if skills else None


class HarborJobParser:
    def __init__(self, job_dir: Path) -> None:
        self.job_dir = job_dir

    def trials(self) -> list[HarborTrial]:
        """Trials in start order. Directory names carry a random suffix, so
        sort by result.json's started_at instead."""
        trials = []
        for result_path in self.job_dir.glob("*/result.json"):
            try:
                result = json.loads(result_path.read_text())
            except json.JSONDecodeError:
                continue
            trials.append(HarborTrial(result_path.parent, result))
        return sorted(trials, key=lambda t: (t.started_at or "", t.path.name))

    def normalize(self, trial: HarborTrial, experiment_id: str, run_id: str) -> tuple[RunRecord, WorkspaceChanges | None]:
        result = trial.result
        exception = result.get("exception_info") or {}
        agent_result = result.get("agent_result") or {}
        agent_info = result.get("agent_info") or {}

        record = RunRecord(
            experiment_id=experiment_id,
            run_id=run_id,
            completed=not exception,
            error=exception.get("exception_message"),
            final_response=None,
            started_at=result.get("started_at"),
            duration_seconds=_seconds(result.get("agent_execution")),
            input_tokens=agent_result.get("n_input_tokens"),
            cache_tokens=agent_result.get("n_cache_tokens"),
            output_tokens=agent_result.get("n_output_tokens"),
            cost_usd=agent_result.get("cost_usd"),
            harbor_trial_name=trial.name,
            harbor_trial_path=str(trial.path),
            trajectory_path=str(trial.trajectory_path) if trial.trajectory_path else None,
            workspace_path=str(trial.workspace_path) if trial.workspace_path else None,
            agent_name=agent_info.get("name"),
            agent_version=agent_info.get("version"),
            model=(agent_info.get("model_info") or {}).get("name"),
        )

        if trial.trajectory_path:
            facts = parse_trajectory(trial.trajectory_path)
            record.tool_calls = facts.tool_calls
            record.commands = facts.commands
            record.final_response = facts.final_response
            record.model = record.model or facts.model
            record.agent_version = record.agent_version or facts.agent_version

        changes = None
        if trial.workspace_path:
            changes = workspace_changes(trial.workspace_path)
            record.files_created = changes.files_created
            record.files_modified = changes.files_modified
            record.files_deleted = changes.files_deleted
            record.diff_stats = changes.stats
        return record, changes


def _seconds(timing: dict | None) -> float | None:
    if not timing or not timing.get("started_at") or not timing.get("finished_at"):
        return None
    start = datetime.fromisoformat(timing["started_at"])
    end = datetime.fromisoformat(timing["finished_at"])
    return (end - start).total_seconds()
