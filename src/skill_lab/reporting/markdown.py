"""report.md: the analysis, written for a skill author to read."""

from __future__ import annotations

from skill_lab.models.analysis import Analysis, Finding
from skill_lab.models.comparison import Comparison
from skill_lab.models.experiment import Manifest
from skill_lab.models.run_record import RunRecord


def _runs(ids: list[str]) -> str:
    return ", ".join(f"#{i.lstrip('0') or '0'}" for i in ids) if ids else "—"


def _findings(title: str, findings: list[Finding]) -> list[str]:
    lines = [f"## {title}", ""]
    if not findings:
        lines += ["None identified.", ""]
        return lines
    for f in findings:
        tag = "" if f.basis == "observed" else " *(inferred)*"
        lines += [f"### {f.title}{tag}", "", f.description, "", f"Runs: {_runs(f.run_ids)}", ""]
    return lines


def render_report(manifest: Manifest, records: list[RunRecord], analysis: Analysis) -> str:
    n = analysis.run_count
    lines = [
        f"# Skill Lab report: {manifest.id}",
        "",
        f"- Skill: `{manifest.skill['name']}` ({manifest.skill['digest']})",
        f"- Agent: {manifest.agent['name']} / {manifest.agent.get('model')}",
        f"- Prompt: {manifest.prompt['text'].strip()}",
        f"- Runs: {analysis.completed_count}/{n} completed",
        f"- Analyzed by: {analysis.model} ({analysis.input_chars} chars of input)",
        "",
        "Counts below are observed behavioral frequencies, not quality scores. "
        "Every finding lists the runs it rests on; `skill-lab inspect <experiment> --run N` shows the evidence.",
        "",
        "## Overview",
        "",
        analysis.overview,
        "",
        "## Execution strategies",
        "",
    ]
    for c in analysis.clusters:
        lines += [f"- **{c.name}** — {len(c.run_ids)}/{n} runs ({_runs(c.run_ids)})", f"  {c.description}"]
    lines.append("")

    lines += _findings("Recurring behavior", analysis.recurring_patterns)
    lines += _findings("Recurring problems", analysis.recurring_problems)
    lines += _findings("Outliers", analysis.outliers)

    lines += ["## Strong runs", ""]
    if not analysis.strong_runs:
        lines += ["None singled out.", ""]
    for s in analysis.strong_runs:
        lines.append(f"- **#{s.run_id.lstrip('0')}**")
        lines += [f"  - {r}" for r in s.reasons]
    lines.append("")

    lines += ["## Observations about SKILL.md", ""]
    lines += [f"- {o}" for o in analysis.skill_observations] or ["None."]
    lines.append("")

    lines += ["## Suggested changes to SKILL.md", ""]
    if not analysis.suggested_changes:
        lines += ["None suggested.", ""]
    for i, c in enumerate(analysis.suggested_changes, 1):
        lines += [f"### {i}. {c.change.splitlines()[0][:80]}", "", f"> {c.change}", "",
                  f"Motivation: {c.motivation}", "", f"Runs: {_runs(c.run_ids)}", ""]

    lines += ["## Run table", "", "| run | ok | secs | tools | files | +lines | -lines | modified/created |",
              "|---|---|---|---|---|---|---|---|"]
    for r in records:
        s = r.diff_stats
        touched = ", ".join(r.files_modified + r.files_created) or "—"
        lines.append(
            f"| {r.run_id} | {'y' if r.completed else 'N'} | "
            f"{f'{r.duration_seconds:.0f}' if r.duration_seconds is not None else '-'} | "
            f"{len(r.tool_calls)} | {s.files_changed if s else '-'} | {s.insertions if s else '-'} | "
            f"{s.deletions if s else '-'} | {touched} |"
        )
    lines.append("")
    return "\n".join(lines)


def frequency_table(c: Comparison) -> str:
    """The §17 table: behavior | A | B, as observed frequencies."""
    w = max((len(b.behavior) for b in c.behaviors), default=8)
    w = min(max(w, 8), 70)
    lines = [f"{'Observation':<{w}}  {c.a_id:>10}  {c.b_id:>10}"]
    for b in c.behaviors:
        name = b.behavior if len(b.behavior) <= w else b.behavior[: w - 1] + "…"
        lines.append(f"{name:<{w}}  {f'{len(b.a_run_ids)}/{c.a_run_count}':>10}  {f'{len(b.b_run_ids)}/{c.b_run_count}':>10}")
    return "\n".join(lines)


def render_comparison(c: Comparison) -> str:
    lines = [
        f"# Skill Lab comparison: {c.a_id} → {c.b_id}",
        "",
        f"- A: `{c.a_id}` — {c.a_run_count} runs, skill {c.a_skill_digest}",
        f"- B: `{c.b_id}` — {c.b_run_count} runs, skill {c.b_skill_digest}",
        f"- Compared by: {c.model} ({c.input_chars} chars of input)",
        "",
    ]
    if c.compatibility_warnings:
        lines += ["> **Warning:** " + "; ".join(c.compatibility_warnings) + ".", ""]
    lines += [
        "Numbers are observed behavioral frequencies (runs exhibiting the behavior), not quality scores.",
        "",
        "## Summary", "", c.summary, "",
        "## Behavior frequencies", "",
        f"| Observation | {c.a_id} | {c.b_id} |", "|---|---|---|",
    ]
    for b in c.behaviors:
        lines.append(f"| {b.behavior} | {len(b.a_run_ids)}/{c.a_run_count} | {len(b.b_run_ids)}/{c.b_run_count} |")
    lines += ["", "<details><summary>Run ids per behavior</summary>", ""]
    for b in c.behaviors:
        lines.append(f"- {b.behavior}: A {_runs(b.a_run_ids)}; B {_runs(b.b_run_ids)}")
    lines += ["", "</details>", ""]
    lines += ["## Behavior consistency", "", f"- {c.a_id}: {c.consistency.get('a', '?')}", f"- {c.b_id}: {c.consistency.get('b', '?')}", ""]
    for title, items in (("Improvements", c.improvements), ("New behavior in B", c.new_behaviors), ("Remaining issues", c.remaining_issues)):
        lines += [f"## {title}", ""] + ([f"- {i}" for i in items] or ["None identified."]) + [""]
    lines += ["## SKILL.md diff", "", "```diff", c.skill_diff.rstrip() or "(no textual difference)", "```", ""]
    return "\n".join(lines)
