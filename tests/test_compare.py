from pathlib import Path

from skill_lab.analysis.compare import ExperimentBundle, compare_experiments, compatibility_warnings, skill_diff
from skill_lab.models.comparison import Comparison
from skill_lab.models.experiment import ExperimentPaths, Manifest
from skill_lab.models.run_record import DiffStats, RunRecord
from skill_lab.models.run_summary import RunSummary
from skill_lab.reporting.markdown import frequency_table, render_comparison


def manifest(id: str, digest: str, **over) -> Manifest:
    base = dict(id=id, created_at="t", skill={"path": "s", "name": "s", "digest": digest},
                repository={"source": "r", "digest": "sha256:fix", "git_commit": "abc", "git_dirty": False},
                agent={"name": "claude-code", "model": "m"}, prompt={"text": "P"},
                execution={"attempts": 2}, harbor={"job_name": id})
    base.update(over)
    return Manifest(**base)


def bundle(tmp_path: Path, id: str, digest: str, skill: str, **over) -> ExperimentBundle:
    m = manifest(id, digest, **over)
    recs = [RunRecord(experiment_id=id, run_id=r, completed=True, error=None, final_response="f", started_at=None,
                      duration_seconds=1.0, input_tokens=1, cache_tokens=1, output_tokens=1, cost_usd=0.0,
                      diff_stats=DiffStats(1, 1, 1)) for r in ("001", "002")]
    sums = [RunSummary(run_id=r, approach="a", steps=[], outcome="o") for r in ("001", "002")]
    return ExperimentBundle(ExperimentPaths(tmp_path / id), m, skill, recs, sums, None)


def test_compatibility_warnings():
    a, b = manifest("a", "d1"), manifest("b", "d2")
    assert compatibility_warnings(a, b) == []
    assert "identical" in compatibility_warnings(a, manifest("b", "d1"))[0]
    w = compatibility_warnings(a, manifest("b", "d2", prompt={"text": "Q"}, agent={"name": "codex", "model": "m"}))
    assert any("prompt" in x for x in w) and any("agent" in x for x in w)
    w = compatibility_warnings(a, manifest("b", "d2", repository={"source": "r", "digest": "sha256:other", "git_commit": "abc"}))
    assert any("fixture differs" in x for x in w)


class FakeModel:
    model = "fake"

    def generate_json(self, system_prompt, prompt, schema):
        assert "SKILL.md diff" in prompt and "-old line" in prompt and "+new line" in prompt
        return {
            "summary": "changed",
            "behaviors": [
                {"behavior": "did X", "a_run_ids": ["1", "002", "1"], "b_run_ids": []},
                {"behavior": "did Y", "a_run_ids": ["009"], "b_run_ids": ["2", "1"]},
            ],
            "consistency": {"a": "low: x", "b": "high: y"},
            "improvements": ["i"], "new_behaviors": [], "remaining_issues": ["r"],
        }


def test_compare_counts_from_ids_and_renders(tmp_path: Path):
    a = bundle(tmp_path, "v1", "d1", "old line\nsame\n")
    b = bundle(tmp_path, "v2", "d2", "new line\nsame\n")
    assert "-old line" in skill_diff(a, b)
    c = compare_experiments(a, b, FakeModel())
    assert c.behaviors[0].a_run_ids == ["001", "002"] and c.behaviors[0].b_run_ids == []
    assert c.behaviors[1].a_run_ids == [] and c.behaviors[1].b_run_ids == ["001", "002"]  # 009 unknown -> dropped
    table = frequency_table(c)
    assert "did X" in table and "2/2" in table and "0/2" in table
    report = render_comparison(c)
    assert "| did Y | 0/2 | 2/2 |" in report and "```diff" in report
    p = tmp_path / "c.json"
    c.save(p)
    assert Comparison.load(p) == c
