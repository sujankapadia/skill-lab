"""report.md: the analysis, written for a skill author to read."""

from __future__ import annotations

from skill_lab.models.analysis import Analysis, Finding
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
