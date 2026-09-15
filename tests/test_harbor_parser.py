from pathlib import Path

from conftest import make_trial
from skill_lab.harbor.parser import HarborJobParser
from skill_lab.harbor.trajectory import parse_trajectory, summarize_call


def test_trials_sorted_by_start_time(tmp_path: Path, workspace: Path):
    job = tmp_path / "job"
    make_trial(job, "task__zzz", "2026-09-14T10:00:00+00:00", workspace)
    make_trial(job, "task__aaa", "2026-09-14T10:05:00+00:00", workspace)
    names = [t.name for t in HarborJobParser(job).trials()]
    assert names == ["task__zzz", "task__aaa"]


def test_normalize_completed_trial(tmp_path: Path, workspace: Path):
    (workspace / "docs" / "architecture.md").write_text("new\n")
    job = tmp_path / "job"
    make_trial(job, "task__abc", "2026-09-14T10:00:00+00:00", workspace)

    trial = HarborJobParser(job).trials()[0]
    record, changes = HarborJobParser(job).normalize(trial, "exp", "001")

    assert record.completed and record.error is None
    assert record.run_id == "001" and record.harbor_trial_name == "task__abc"
    assert record.duration_seconds == 30.0
    assert (record.input_tokens, record.output_tokens, record.cost_usd) == (100, 10, 0.01)
    assert record.model == "claude-sonnet-5" and record.agent_version == "2.1.270"
    assert [tc.name for tc in record.tool_calls] == ["Skill", "Bash", "Read", "Write"]
    assert record.commands == ["find . -maxdepth 2"]
    assert record.final_response == "I rewrote docs/architecture.md."
    assert record.files_modified == ["docs/architecture.md"]
    assert record.diff_stats.files_changed == 1
    assert changes is not None and "architecture.md" in changes.patch
    assert trial.skill_digest == "sha256:abc"


def test_normalize_failed_trial_without_workspace(tmp_path: Path):
    job = tmp_path / "job"
    make_trial(job, "task__t", "2026-09-14T10:00:00+00:00", None,
               exception={"exception_type": "TimeoutError", "exception_message": "Agent execution timed out"})
    trial = HarborJobParser(job).trials()[0]
    record, changes = HarborJobParser(job).normalize(trial, "exp", "001")
    assert not record.completed
    assert record.error == "Agent execution timed out"
    assert record.workspace_path is None and changes is None
    assert record.diff_stats is None
    # Partial trajectory is still usable.
    assert len(record.tool_calls) == 4


def test_summarize_call():
    assert summarize_call("Bash", {"command": "ls  -la\n", "description": "x"}) == "ls -la"
    assert summarize_call("Read", {"file_path": "/app/x"}) == "/app/x"
    assert summarize_call("Weird", {"b": 1, "a": 2}) == '{"a": 2, "b": 1}'
    assert summarize_call("Weird", None) == ""
    assert summarize_call("Bash", {"command": "x" * 300}).endswith("…")


def test_normalize_interactive_trial_converts_native_session(tmp_path: Path, workspace: Path):
    import json
    from test_claude_session import _write_session
    job = tmp_path / "job"
    trial = make_trial(job, "task__i", "2026-09-14T10:00:00+00:00", workspace)
    (trial / "agent" / "trajectory.json").unlink()          # ACP mode: Harbor writes no ATIF
    (trial / "user-agent").mkdir()
    _write_session(trial)                                    # ...but the native session is there
    run_dir = tmp_path / "runs" / "001"
    run_dir.mkdir(parents=True)
    parser = HarborJobParser(job)
    record, _ = parser.normalize(parser.trials()[0], "exp", "001", run_dir)
    assert record.interactive is True
    assert record.trajectory_path == str(run_dir / "trajectory.json")
    assert [tc.name for tc in record.tool_calls] == ["Bash"]
    assert record.awaiting_input is True


def test_trajectory_is_copied_into_the_run_dir(tmp_path: Path, workspace: Path):
    """Headless trials: runs/NNN/ owns a copy, so the run survives deletion of
    the Harbor job directory."""
    import json
    import shutil
    job = tmp_path / "job"
    make_trial(job, "task__c", "2026-09-14T10:00:00+00:00", workspace)
    run_dir = tmp_path / "runs" / "001"
    run_dir.mkdir(parents=True)
    parser = HarborJobParser(job)
    trial = parser.trials()[0]
    record, _ = parser.normalize(trial, "exp", "001", run_dir)

    copied = run_dir / "trajectory.json"
    assert record.trajectory_path == str(copied)
    assert record.harbor_trajectory_path == str(trial.trajectory_path)
    assert json.loads(copied.read_text()) == json.loads(trial.trajectory_path.read_text())

    # The copy is still readable once Harbor's job directory is gone.
    shutil.rmtree(job)
    assert json.loads(copied.read_text())["schema_version"] == "ATIF-v1.7"
