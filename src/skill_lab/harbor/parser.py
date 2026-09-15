"""Read a Harbor job directory and normalize each trial into a RunRecord.

This is the only module that knows Harbor's on-disk layout (documented in
docs/harbor-spike.md). The rest of Skill Lab works with RunRecords.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from skill_lab.harbor.claude_session import convert_session, find_session_files
from skill_lab.harbor.trajectory import parse_trajectory
from skill_lab.models.run_record import RunRecord
from skill_lab.workspace.git_diff import WorkspaceChanges, workspace_changes

WORKSPACE_ARTIFACT = "app"  # mirrors the container's /app
TRAJECTORY_FILENAME = "trajectory.json"


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
    def user_trajectory_path(self) -> Path | None:
        p = self.path / "user-agent" / "trajectory.json"
        return p if p.exists() else None

    @property
    def is_interactive(self) -> bool:
        return (self.path / "user-agent").is_dir()

    def ensure_trajectory(self, out_dir: Path) -> Path | None:
        """Write this trial's trajectory into out_dir and return the path.

        Headless trials: copy Harbor's ATIF. ACP/simulated-user trials: Harbor
        writes none for the target, so convert the native Claude Code session.

        The trajectory is the evidence every later stage reads, and it is small
        (~100 KB/run against ~850 KB/run for the whole trial directory), so
        runs/ owns a copy. That keeps a run re-summarizable and re-analyzable
        after the bulky harbor/ job directory is deleted or the experiment is
        moved. Workspaces stay referenced in place — those are the large ones.
        """
        out = out_dir / TRAJECTORY_FILENAME
        if self.trajectory_path:
            shutil.copyfile(self.trajectory_path, out)
            return out
        sessions = find_session_files(self.path / "agent")
        if not sessions:
            return None
        out.write_text(json.dumps(convert_session(sessions), indent=2))
        return out

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

    def normalize(
        self, trial: HarborTrial, experiment_id: str, run_id: str, run_dir: Path | None = None
    ) -> tuple[RunRecord, WorkspaceChanges | None]:
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
            trajectory_path=None,
            harbor_trajectory_path=str(trial.trajectory_path) if trial.trajectory_path else None,
            workspace_path=str(trial.workspace_path) if trial.workspace_path else None,
            agent_name=agent_info.get("name"),
            agent_version=agent_info.get("version"),
            model=(agent_info.get("model_info") or {}).get("name"),
            interactive=trial.is_interactive,
            user_trajectory_path=str(trial.user_trajectory_path) if trial.user_trajectory_path else None,
        )

        trajectory = trial.ensure_trajectory(run_dir) if run_dir else trial.trajectory_path
        if trajectory:
            record.trajectory_path = str(trajectory)
            facts = parse_trajectory(trajectory)
            record.tool_calls = facts.tool_calls
            record.commands = facts.commands
            record.final_response = facts.final_response
            record.model = record.model or facts.model
            record.agent_version = record.agent_version or facts.agent_version
            record.user_turns = facts.user_turns
            record.awaiting_input = facts.awaiting_input
            if record.input_tokens is None and facts.final_metrics:
                record.input_tokens = facts.final_metrics.get("total_prompt_tokens")
                record.cache_tokens = facts.final_metrics.get("total_cached_tokens")
                record.output_tokens = facts.final_metrics.get("total_completion_tokens")

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
