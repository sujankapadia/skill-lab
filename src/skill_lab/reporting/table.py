"""Plain-text views of run records for `skill-lab inspect`."""

from __future__ import annotations

from skill_lab.models.analysis import Analysis
from skill_lab.models.experiment import Manifest
from skill_lab.models.run_record import RunRecord
from skill_lab.models.run_summary import RunSummary


def _fmt(value, spec: str = "") -> str:
    return "-" if value is None else format(value, spec)


def runs_table(records: list[RunRecord]) -> str:
    header = (
        f"{'RUN':<4} {'OK':<3} {'TIME':>6} {'TOOLS':>5} {'CMDS':>4} {'FILES':>5} "
        f"{'+LINES':>6} {'-LINES':>6} {'IN_TOK':>8} {'OUT_TOK':>8} {'COST':>7}"
    )
    interactive = any(r.interactive for r in records)
    if interactive:
        header += f" {'REPLIES':>7} {'WAITING':>7}"
    lines = [header]
    for r in records:
        stats = r.diff_stats
        tail = f" {r.user_turns:>7} {'yes' if r.awaiting_input else 'no':>7}" if interactive else ""
        lines.append(
            f"{r.run_id:<4} {'y' if r.completed else 'N':<3} "
            f"{_fmt(r.duration_seconds, '.0f') + ('s' if r.duration_seconds is not None else ''):>6} "
            f"{len(r.tool_calls):>5} {len(r.commands):>4} "
            f"{_fmt(stats.files_changed if stats else None):>5} "
            f"{_fmt(stats.insertions if stats else None):>6} "
            f"{_fmt(stats.deletions if stats else None):>6} "
            f"{_fmt(r.input_tokens):>8} {_fmt(r.output_tokens):>8} "
            f"{('$' + format(r.cost_usd, '.2f')) if r.cost_usd is not None else '-':>7}" + tail
        )
    return "\n".join(lines)


def experiment_header(manifest: Manifest, records: list[RunRecord]) -> str:
    completed = sum(1 for r in records if r.completed)
    return "\n".join([
        f"Experiment: {manifest.id}",
        f"Skill:      {manifest.skill['name']}  ({manifest.skill['digest']})",
        f"Agent:      {manifest.agent['name']}  model={manifest.agent.get('model')}  auth={manifest.agent.get('auth')}",
        (f"Persona:    {(manifest.prompt.get('persona') or '').strip().splitlines()[0][:100]}  [interactive, user model {manifest.agent.get('user_model')}]"
         if manifest.agent.get("interactive") else f"Prompt:     {manifest.prompt['text'].strip().splitlines()[0][:100]}"),
        f"Runs:       {completed}/{len(records)} completed",
    ])


def run_detail(r: RunRecord) -> str:
    lines = [
        f"=== Run {r.run_id} ({r.harbor_trial_name}) ===",
        f"completed:  {r.completed}" + (f"  error: {r.error}" if r.error else ""),
        f"duration:   {_fmt(r.duration_seconds, '.0f')}s   tokens in/out: {_fmt(r.input_tokens)}/{_fmt(r.output_tokens)}   cost: ${_fmt(r.cost_usd, '.2f')}",
        f"created:    {r.files_created}",
        f"modified:   {r.files_modified}",
        f"deleted:    {r.files_deleted}",
        "tool calls:",
    ]
    for tc in r.tool_calls:
        lines.append(f"  {tc.step_id:>3}  {tc.name:<12} {tc.summary}")
    resp = (r.final_response or "").strip()
    lines.append("final response:")
    lines.append("  " + resp.replace("\n", "\n  ") if resp else "  (none)")
    lines.append(f"trajectory: {r.trajectory_path}")
    lines.append(f"workspace:  {r.workspace_path}")
    return "\n".join(lines)


def summary_detail(s: RunSummary) -> str:
    def block(title: str, items: list[str]) -> list[str]:
        return [f"{title}:"] + ([f"  - {i}" for i in items] or ["  (none)"])

    lines = [f"--- Summary (by {s.model}, {s.evidence_chars} chars of evidence) ---",
             f"approach: {s.approach}",
             f"outcome:  {s.outcome}"]
    lines += block("steps", s.steps)
    lines += block("notable behaviors", s.notable_behaviors)
    lines += block("possible problems", s.possible_problems)
    lines += block("strengths", s.strengths)
    lines += block("uncertainties", s.uncertainties)
    return "\n".join(lines)


def analysis_brief(a: Analysis) -> str:
    """The §23 terminal view: strategies, headline problems, strong runs, suggestions."""
    def ids(xs: list[str]) -> str:
        return ", ".join("#" + x.lstrip("0") for x in xs) if xs else "—"

    lines = [a.overview.strip(), "", f"{len(a.clusters)} execution strategies emerged:"]
    for c in a.clusters:
        lines.append(f"  {c.name:<28} {len(c.run_ids):>2}/{a.run_count} runs   {c.description}")
    if a.recurring_problems:
        lines += ["", "Recurring concerns:"]
        for f in a.recurring_problems:
            lines.append(f"  - {f.title} ({len(f.run_ids)} runs: {ids(f.run_ids)})")
    if a.outliers:
        lines += ["", "Outliers:"]
        for f in a.outliers:
            lines.append(f"  - {f.title} ({ids(f.run_ids)})")
    if a.strong_runs:
        lines += ["", "Strong runs: " + ids([s.run_id for s in a.strong_runs])]
        for s in a.strong_runs[:3]:
            for r in s.reasons[:2]:
                lines.append(f"  #{s.run_id.lstrip('0')}: {r}")
    if a.skill_observations:
        lines += ["", "Likely skill ambiguities:"]
        lines += [f"  - {o}" for o in a.skill_observations]
    if a.suggested_changes:
        lines += ["", "Suggested SKILL.md changes:"]
        for i, c in enumerate(a.suggested_changes, 1):
            lines.append(f"  {i}. {c.change}")
            lines.append(f"     because: {c.motivation} ({ids(c.run_ids)})")
    return "\n".join(lines)
