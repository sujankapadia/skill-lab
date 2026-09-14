from pathlib import Path

import pytest

from skill_lab.analysis.analyze_runs import analyze_runs, build_analysis_input, facts_table
from skill_lab.models.analysis import Analysis
from skill_lab.models.run_record import DiffStats, RunRecord, ToolCall
from skill_lab.models.run_summary import RunSummary


def rec(run_id: str, **kw) -> RunRecord:
    base = dict(experiment_id="e", run_id=run_id, completed=True, error=None, final_response="done",
                started_at=None, duration_seconds=30.0, input_tokens=1, cache_tokens=1, output_tokens=1,
                cost_usd=0.1, tool_calls=[ToolCall(1, "Bash", "ls")], commands=["ls"],
                files_modified=["docs/architecture.md"], diff_stats=DiffStats(1, 10, 2))
    base.update(kw)
    return RunRecord(**base)


def summ(run_id: str) -> RunSummary:
    return RunSummary(run_id=run_id, approach=f"approach {run_id}", steps=["s1"], outcome="o",
                      notable_behaviors=["n"], possible_problems=["Observed: p"], strengths=[], uncertainties=[])


def test_facts_table_and_input():
    records = [rec("001"), rec("002", completed=False, error="timeout", diff_stats=None, files_modified=[])]
    text = build_analysis_input("P", "S", records, [summ("001"), summ("002")])
    assert "N (timeout)" in facts_table(records)
    assert "## Run 001" in text and "## Run 002" in text
    assert "approach 002" in text


def test_input_requires_all_summaries():
    with pytest.raises(ValueError, match="002"):
        build_analysis_input("P", "S", [rec("001"), rec("002")], [summ("001")])


class FakeModel:
    model = "fake"

    def generate_json(self, system_prompt, prompt, schema):
        assert "not to declare the skill correct" in system_prompt
        return {
            "overview": "ov",
            "clusters": [{"name": "a", "description": "d", "run_ids": ["1", "#2", "003", "999"]}],
            "recurring_patterns": [{"title": "t", "description": "d", "run_ids": ["run 2"], "basis": "observed"}],
            "recurring_problems": [],
            "outliers": [{"title": "o", "description": "d", "run_ids": ["3", "3"], "basis": "inferred"}],
            "strong_runs": [{"run_id": "2", "reasons": ["r"]}],
            "skill_observations": ["obs"],
            "suggested_changes": [{"change": "c", "motivation": "m", "run_ids": ["1"]}],
        }


def test_analyze_runs_normalizes_ids_and_round_trips(tmp_path: Path):
    records = [rec("001"), rec("002"), rec("003")]
    a = analyze_runs("exp", "P", "S", records, [summ("001"), summ("002"), summ("003")], FakeModel())
    assert a.run_count == 3 and a.completed_count == 3
    assert a.clusters[0].run_ids == ["001", "002", "003"]       # unknown 999 dropped, forms normalized
    assert a.recurring_patterns[0].run_ids == ["002"]
    assert a.outliers[0].run_ids == ["003"] and a.outliers[0].basis == "inferred"
    assert a.strong_runs[0].run_id == "002"
    assert a.suggested_changes[0].run_ids == ["001"]
    p = tmp_path / "analysis.json"
    a.save(p)
    assert Analysis.load(p) == a
