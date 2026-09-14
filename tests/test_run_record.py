from pathlib import Path

from skill_lab.models.run_record import DiffStats, RunRecord, ToolCall


def test_round_trip(tmp_path: Path):
    r = RunRecord(
        experiment_id="e", run_id="001", completed=True, error=None, final_response="done",
        started_at="2026-09-14T10:00:00+00:00", duration_seconds=1.5,
        input_tokens=1, cache_tokens=2, output_tokens=3, cost_usd=0.5,
        tool_calls=[ToolCall(2, "Bash", "ls")], commands=["ls"],
        files_created=["a"], diff_stats=DiffStats(1, 2, 3), harbor_trial_path="/t",
    )
    p = tmp_path / "run.json"
    r.save(p)
    assert RunRecord.load(p) == r


def test_round_trip_without_diff(tmp_path: Path):
    r = RunRecord(experiment_id="e", run_id="001", completed=False, error="boom", final_response=None,
                  started_at=None, duration_seconds=None, input_tokens=None, cache_tokens=None,
                  output_tokens=None, cost_usd=None)
    p = tmp_path / "run.json"
    r.save(p)
    assert RunRecord.load(p) == r
