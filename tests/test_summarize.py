import json
from pathlib import Path

from conftest import TRAJECTORY, make_trial
from skill_lab.analysis.evidence import EvidenceLimits, build_evidence, observation_text
from skill_lab.analysis.summarize_run import summarize_run
from skill_lab.harbor.parser import HarborJobParser
from skill_lab.models.run_summary import RUN_SUMMARY_SCHEMA, RunSummary


def _record(tmp_path: Path, workspace: Path):
    (workspace / "docs" / "architecture.md").write_text("new\n")
    job = tmp_path / "job"
    make_trial(job, "task__abc", "2026-09-14T10:00:00+00:00", workspace)
    parser = HarborJobParser(job)
    record, changes = parser.normalize(parser.trials()[0], "exp", "001")
    patch = tmp_path / "diff.patch"
    patch.write_text(changes.patch)
    record.diff_patch_path = str(patch)
    return record


def test_evidence_contains_all_sections(tmp_path: Path, workspace: Path):
    record = _record(tmp_path, workspace)
    ev = build_evidence(record, "Do the thing.", "# SKILL\nbe good")
    assert "# Task prompt given to the agent\nDo the thing." in ev
    assert "# SKILL.md that was active\n# SKILL\nbe good" in ev
    assert "Skill architecture-documentation" in ev
    assert "$ find . -maxdepth 2" in ev
    assert "Read /app/docs/architecture.md" in ev
    assert "Write /app/docs/architecture.md\n    new" in ev
    assert "# Final response from the agent\nI rewrote docs/architecture.md." in ev
    assert "modified: ['docs/architecture.md']" in ev
    assert "## Diff" in ev and "+new" in ev


def test_evidence_truncation_is_marked(tmp_path: Path, workspace: Path):
    record = _record(tmp_path, workspace)
    ev = build_evidence(record, "p", "s", EvidenceLimits(patch_chars=20))
    assert "more chars]" in ev


def test_observation_text_prefers_clean_stdout():
    result = {
        "content": "out\n\n[stdout]\nout",
        "extra": {"tool_result_metadata": {"tool_use_result": {"stdout": "out", "stderr": "warn"}}},
    }
    assert observation_text(result) == "out\n[stderr] warn"
    assert observation_text({"content": "plain"}) == "plain"
    assert observation_text({"content": [{"type": "text", "text": "part"}]}) == "part"
    assert observation_text({"content": ""}) == "(no output)"


class FakeModel:
    model = "fake"

    def __init__(self):
        self.calls = []

    def generate_json(self, system_prompt, prompt, schema):
        self.calls.append((system_prompt, prompt, schema))
        return {
            "approach": "did a thing", "steps": ["a", "b"], "outcome": "changed a file",
            "notable_behaviors": ["x"], "possible_problems": [], "strengths": ["Observed: y"],
            "uncertainties": ["z"],
        }


def test_summarize_run_uses_prompt_and_schema(tmp_path: Path, workspace: Path):
    record = _record(tmp_path, workspace)
    model = FakeModel()
    summary = summarize_run(record, "Prompt!", "Skill!", model)
    system_prompt, prompt, schema = model.calls[0]
    assert "not to grade it" in system_prompt
    assert "Prompt!" in prompt and "Skill!" in prompt
    assert schema is RUN_SUMMARY_SCHEMA
    assert summary.run_id == "001" and summary.model == "fake"
    assert summary.steps == ["a", "b"] and summary.evidence_chars == len(prompt)

    p = tmp_path / "summary.json"
    summary.save(p)
    assert RunSummary.load(p) == summary
