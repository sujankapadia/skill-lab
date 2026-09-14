"""Plain-text views of run records for `skill-lab inspect`."""

from __future__ import annotations

from skill_lab.models.experiment import Manifest
from skill_lab.models.run_record import RunRecord


def _fmt(value, spec: str = "") -> str:
    return "-" if value is None else format(value, spec)


def runs_table(records: list[RunRecord]) -> str:
    header = (
        f"{'RUN':<4} {'OK':<3} {'TIME':>6} {'TOOLS':>5} {'CMDS':>4} {'FILES':>5} "
        f"{'+LINES':>6} {'-LINES':>6} {'IN_TOK':>8} {'OUT_TOK':>8} {'COST':>7}"
    )
    lines = [header]
    for r in records:
        stats = r.diff_stats
        lines.append(
            f"{r.run_id:<4} {'y' if r.completed else 'N':<3} "
            f"{_fmt(r.duration_seconds, '.0f') + ('s' if r.duration_seconds is not None else ''):>6} "
            f"{len(r.tool_calls):>5} {len(r.commands):>4} "
            f"{_fmt(stats.files_changed if stats else None):>5} "
            f"{_fmt(stats.insertions if stats else None):>6} "
            f"{_fmt(stats.deletions if stats else None):>6} "
            f"{_fmt(r.input_tokens):>8} {_fmt(r.output_tokens):>8} "
            f"{('$' + format(r.cost_usd, '.2f')) if r.cost_usd is not None else '-':>7}"
        )
    return "\n".join(lines)


def experiment_header(manifest: Manifest, records: list[RunRecord]) -> str:
    completed = sum(1 for r in records if r.completed)
    return "\n".join([
        f"Experiment: {manifest.id}",
        f"Skill:      {manifest.skill['name']}  ({manifest.skill['digest']})",
        f"Agent:      {manifest.agent['name']}  model={manifest.agent.get('model')}  auth={manifest.agent.get('auth')}",
        f"Prompt:     {manifest.prompt['text'].strip().splitlines()[0][:100]}",
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
