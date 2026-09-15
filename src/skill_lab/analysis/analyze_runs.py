"""Cross-run analysis: RunRecords + RunSummaries -> Analysis (§13)."""

from __future__ import annotations

import json

from skill_lab.analysis.model import AnalysisModel
from skill_lab.analysis.summarize_run import load_prompt
from skill_lab.models.analysis import (
    ANALYSIS_SCHEMA,
    Analysis,
    Cluster,
    Finding,
    StrongRun,
    SuggestedChange,
)
from skill_lab.models.run_record import RunRecord
from skill_lab.models.run_summary import RunSummary

# A compact summary is ~2k chars, so 50 runs is ~100k chars (~25k tokens):
# one call is fine for the MVP's 20-50 range. Guard rather than silently
# overflow; hierarchical batching (§16) can come when a real experiment needs it.
MAX_INPUT_CHARS = 400_000


def facts_table(records: list[RunRecord]) -> str:
    interactive = any(r.interactive for r in records)
    header = "run | ok | secs | tools | bash | files | +lines | -lines | created | modified | deleted"
    if interactive:
        header += " | user_replies | ended_awaiting_input"
    lines = [header]
    for r in records:
        s = r.diff_stats
        extra = [str(r.user_turns), "yes" if r.awaiting_input else "no"] if interactive else []
        lines.append(" | ".join([
            r.run_id,
            "y" if r.completed else f"N ({r.error})",
            f"{r.duration_seconds:.0f}" if r.duration_seconds is not None else "-",
            str(len(r.tool_calls)),
            str(len(r.commands)),
            str(s.files_changed) if s else "-",
            str(s.insertions) if s else "-",
            str(s.deletions) if s else "-",
            ",".join(r.files_created) or "-",
            ",".join(r.files_modified) or "-",
            ",".join(r.files_deleted) or "-",
            *extra,
        ]))
    return "\n".join(lines)


def _summary_block(s: RunSummary) -> str:
    def items(title: str, xs: list[str]) -> list[str]:
        return [f"{title}:"] + [f"  - {x}" for x in xs] if xs else []

    lines = [f"## Run {s.run_id}", f"approach: {s.approach}", f"outcome: {s.outcome}"]
    lines += items("steps", s.steps)
    lines += items("notable_behaviors", s.notable_behaviors)
    lines += items("possible_problems", s.possible_problems)
    lines += items("strengths", s.strengths)
    lines += items("uncertainties", s.uncertainties)
    return "\n".join(lines)


def build_analysis_input(
    prompt: str,
    skill_md: str,
    records: list[RunRecord],
    summaries: list[RunSummary],
) -> str:
    by_id = {s.run_id: s for s in summaries}
    missing = [r.run_id for r in records if r.run_id not in by_id]
    if missing:
        raise ValueError(f"runs without summaries: {missing}; run `skill-lab summarize` first")

    started = sorted(r.started_at for r in records if r.started_at)
    parts = [
        "# Task prompt given to the agent in every run",
        prompt.strip(),
        "",
        "# Environment",
        f"Runs executed between {started[0] if started else '?'} and {started[-1] if started else '?'} on a UTC clock; "
        "that is the agent's 'today'. Do not judge dates against any other notion of the current date.",
        "",
        "# SKILL.md active in every run",
        skill_md.strip(),
        "",
        f"# Per-run facts ({len(records)} runs)",
        facts_table(records),
        "",
        "# Per-run behavioral summaries",
    ]
    for r in records:
        parts.append(_summary_block(by_id[r.run_id]))
        parts.append("")
    text = "\n".join(parts)
    if len(text) > MAX_INPUT_CHARS:
        raise ValueError(
            f"analysis input is {len(text)} chars (> {MAX_INPUT_CHARS}); "
            "hierarchical summarization is not implemented yet"
        )
    return text


def analyze_runs(
    experiment_id: str,
    prompt: str,
    skill_md: str,
    records: list[RunRecord],
    summaries: list[RunSummary],
    model: AnalysisModel,
) -> Analysis:
    text = build_analysis_input(prompt, skill_md, records, summaries)
    result = model.generate_json(
        system_prompt=load_prompt("analyze-runs"),
        prompt=text,
        schema=ANALYSIS_SCHEMA,
    )
    known = {r.run_id for r in records}
    return Analysis(
        experiment_id=experiment_id,
        run_count=len(records),
        completed_count=sum(1 for r in records if r.completed),
        overview=result["overview"],
        clusters=[Cluster(c["name"], c["description"], _ids(c["run_ids"], known)) for c in result["clusters"]],
        recurring_patterns=[_finding(f, known) for f in result["recurring_patterns"]],
        recurring_problems=[_finding(f, known) for f in result["recurring_problems"]],
        outliers=[_finding(f, known) for f in result["outliers"]],
        strong_runs=[StrongRun(_id(s["run_id"]), list(s["reasons"])) for s in result["strong_runs"]],
        skill_observations=list(result["skill_observations"]),
        suggested_changes=[
            SuggestedChange(c["change"], c["motivation"], _ids(c["run_ids"], known))
            for c in result["suggested_changes"]
        ],
        model=getattr(model, "model", None),
        input_chars=len(text),
    )


def _id(run_id: str) -> str:
    """Normalize '3' / 'run 3' / '#3' to '003'."""
    digits = "".join(ch for ch in str(run_id) if ch.isdigit())
    return digits.zfill(3) if digits else str(run_id)


def _ids(run_ids: list[str], known: set[str]) -> list[str]:
    seen: list[str] = []
    for rid in run_ids:
        norm = _id(rid)
        if norm in known and norm not in seen:
            seen.append(norm)
    return seen


def _finding(f: dict, known: set[str]) -> Finding:
    return Finding(f["title"], f["description"], _ids(f["run_ids"], known), f.get("basis", "observed"))


def describe_json(analysis: Analysis) -> str:
    return json.dumps(analysis.to_dict(), indent=2)
