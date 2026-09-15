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


def test_looks_like_placeholder():
    from skill_lab.analysis.model import looks_like_placeholder
    assert looks_like_placeholder({"approach": "test", "steps": ["a", "b", "c"], "outcome": "test"})
    assert looks_like_placeholder({"approach": "test", "steps": ["test"]})
    assert not looks_like_placeholder({
        "approach": "The agent explored the repo and rewrote the architecture doc.",
        "steps": ["ran find to list files", "read docs/architecture.md", "wrote the new doc"],
        "outcome": "docs/architecture.md rewritten, +80 -3",
        "possible_problems": [],
    })


class UsageModel(FakeModel):
    """A backend that reports usage, like ClaudeCliModel."""

    def generate(self, system_prompt, prompt, schema):
        from skill_lab.analysis.model import ModelUsage
        return self.generate_json(system_prompt, prompt, schema), ModelUsage(1000, 900, 50, 0.02)


def test_summary_records_usage_when_the_backend_reports_it(tmp_path: Path, workspace: Path):
    from skill_lab.models.run_summary import RunSummary
    record = _record(tmp_path, workspace)

    plain = summarize_run(record, "p", "s", FakeModel())
    assert plain.usage is None                      # backend without usage support

    summary = summarize_run(record, "p", "s", UsageModel())
    assert summary.usage.input_tokens == 1000 and summary.usage.cost_usd == 0.02
    p = tmp_path / "summary.json"
    summary.save(p)
    assert RunSummary.load(p) == summary            # survives the round trip


def test_usage_from_claude_envelope():
    from skill_lab.analysis.model import _usage_from_envelope
    u = _usage_from_envelope({
        "usage": {"input_tokens": 4, "cache_creation_input_tokens": 100,
                  "cache_read_input_tokens": 900, "output_tokens": 50},
        "total_cost_usd": 0.02,
    })
    assert (u.input_tokens, u.cache_tokens, u.output_tokens, u.cost_usd) == (1004, 900, 50, 0.02)
    assert _usage_from_envelope({}) is None
