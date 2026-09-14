import json
import shutil
import subprocess
from pathlib import Path

import pytest


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A git repo with a baseline commit, mimicking a downloaded /app artifact."""
    ws = tmp_path / "app"
    ws.mkdir()
    (ws / "README.md").write_text("# App\n")
    (ws / "docs").mkdir()
    (ws / "docs" / "architecture.md").write_text("old\nstale\n")
    (ws / "src").mkdir()
    (ws / "src" / "main.py").write_text("print('hi')\n")
    git(ws, "init", "-q")
    git(ws, "config", "user.email", "t@example.invalid")
    git(ws, "config", "user.name", "t")
    git(ws, "add", "-A")
    git(ws, "commit", "-qm", "baseline")
    return ws


TRAJECTORY = {
    "schema_version": "ATIF-v1.7",
    "session_id": "s",
    "agent": {"name": "claude-code", "version": "2.1.270", "model_name": "claude-sonnet-5"},
    "steps": [
        {"step_id": 1, "source": "user", "message": "Create architecture documentation."},
        {"step_id": 2, "source": "agent", "message": "", "model_name": "claude-sonnet-5",
         "tool_calls": [{"tool_call_id": "a", "function_name": "Skill", "arguments": {"skill": "architecture-documentation"}}]},
        {"step_id": 3, "source": "user", "message": "Base directory for this skill: ..."},
        {"step_id": 4, "source": "agent", "message": "Exploring.", "model_name": "claude-sonnet-5",
         "tool_calls": [
             {"tool_call_id": "b", "function_name": "Bash", "arguments": {"command": "find . -maxdepth 2", "description": "list"}},
             {"tool_call_id": "c", "function_name": "Read", "arguments": {"file_path": "/app/docs/architecture.md"}},
         ]},
        {"step_id": 5, "source": "agent", "message": "I rewrote docs/architecture.md.", "model_name": "claude-sonnet-5",
         "tool_calls": [{"tool_call_id": "d", "function_name": "Write",
                         "arguments": {"file_path": "/app/docs/architecture.md", "content": "new"}}]},
    ],
    "final_metrics": {"total_prompt_tokens": 100, "total_completion_tokens": 10, "total_cost_usd": 0.01, "total_steps": 5},
}


def make_trial(job_dir: Path, name: str, started_at: str, workspace_src: Path | None, exception: dict | None = None) -> Path:
    trial = job_dir / name
    (trial / "agent").mkdir(parents=True)
    (trial / "agent" / "trajectory.json").write_text(json.dumps(TRAJECTORY))
    (trial / "lock.json").write_text(json.dumps({"skills": [{"name": "s", "source": "/x", "digest": "sha256:abc"}]}))
    result = {
        "trial_name": name,
        "started_at": started_at,
        "agent_info": {"name": "claude-code", "version": "2.1.270", "model_info": {"name": "claude-sonnet-5"}},
        "agent_result": {"n_input_tokens": 100, "n_cache_tokens": 80, "n_output_tokens": 10, "cost_usd": 0.01},
        "agent_execution": {"started_at": "2026-09-14T10:00:00+00:00", "finished_at": "2026-09-14T10:00:30+00:00"},
        "exception_info": exception,
    }
    (trial / "result.json").write_text(json.dumps(result))
    if workspace_src is not None:
        shutil.copytree(workspace_src, trial / "artifacts" / "app")
    return trial
