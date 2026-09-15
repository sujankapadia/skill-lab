"""Render one run's evidence as text for the summarizer.

Reads the full ATIF trajectory (not the truncated RunRecord summaries) and
applies per-item caps so a run with large file reads still fits comfortably
in one model call.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from skill_lab.harbor.trajectory import message_text
from skill_lab.models.run_record import RunRecord


@dataclass
class EvidenceLimits:
    message_chars: int = 1500      # agent prose per step
    command_chars: int = 1000      # Bash command text
    write_chars: int = 1500        # Write content / Edit old+new
    observation_chars: int = 1500  # tool output per call (fixture files are ~1k)
    patch_chars: int = 8000        # workspace diff
    final_response_chars: int = 3000


def _clip(text: str, limit: int) -> str:
    text = text.rstrip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + f"\n… [{len(text) - limit} more chars]"


def _call_lines(name: str, args: dict, limits: EvidenceLimits) -> list[str]:
    if name == "Bash":
        return [f"  $ {_clip(args.get('command', ''), limits.command_chars)}"]
    if name in ("Read", "Glob", "Grep"):
        key = "file_path" if name == "Read" else "pattern"
        extra = f" in {args['path']}" if args.get("path") else ""
        return [f"  {name} {args.get(key, '')}{extra}"]
    if name == "Write":
        return [f"  Write {args.get('file_path', '')}",
                _indent(_clip(str(args.get("content", "")), limits.write_chars), 4)]
    if name in ("Edit", "MultiEdit"):
        lines = [f"  {name} {args.get('file_path', '')}"]
        edits = args.get("edits") or [args]
        for e in edits:
            lines.append("    - old: " + _clip(str(e.get("old_string", "")), limits.write_chars // 2).replace("\n", "\n           "))
            lines.append("    + new: " + _clip(str(e.get("new_string", "")), limits.write_chars // 2).replace("\n", "\n           "))
        return lines
    if name == "Skill":
        return [f"  Skill {args.get('skill', '')}"]
    compact = json.dumps(args, sort_keys=True)
    return [f"  {name} {_clip(compact, limits.command_chars)}"]


def _indent(text: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line for line in text.splitlines())


def trajectory_evidence(trajectory_path: Path, limits: EvidenceLimits) -> str:
    traj = json.loads(trajectory_path.read_text())
    out: list[str] = []
    for step in traj.get("steps", []):
        sid = step.get("step_id")
        if step.get("source") == "user":
            text = message_text(step.get("message")).strip()
            if text.startswith("Base directory for this skill"):
                continue  # SKILL.md injection; already shown above
            if text:
                out.append(f"[step {sid}] USER: {_clip(text, limits.message_chars)}")
            continue
        if step.get("source") != "agent":
            continue
        text = message_text(step.get("message")).strip()
        if text:
            out.append(f"[step {sid}] agent: {_clip(text, limits.message_chars)}")
        calls = step.get("tool_calls") or []
        results = {r.get("source_call_id"): r for r in (step.get("observation") or {}).get("results", [])}
        for call in calls:
            name = call.get("function_name") or "?"
            out.append(f"[step {sid}] tool call:")
            out.extend(_call_lines(name, call.get("arguments") or {}, limits))
            result = results.get(call.get("tool_call_id"))
            if result is not None:
                out.append("  → " + _clip(observation_text(result), limits.observation_chars).replace("\n", "\n    "))
    return "\n".join(out)


def observation_text(result: dict) -> str:
    """Tool output for one call.

    Harbor's Claude Code conversion appends a duplicate "[stdout]" block to
    Bash results; the clean stdout/stderr live under extra.tool_result_metadata.
    """
    meta = ((result.get("extra") or {}).get("tool_result_metadata") or {}).get("tool_use_result")
    if isinstance(meta, dict) and "stdout" in meta:
        text = meta.get("stdout") or ""
        if meta.get("stderr"):
            text += f"\n[stderr] {meta['stderr']}"
        return text.strip() or "(no output)"
    content = result.get("content")
    text = content if isinstance(content, str) else message_text(content)
    return text.strip() or "(no output)"


def build_evidence(
    record: RunRecord,
    prompt: str,
    skill_md: str,
    limits: EvidenceLimits | None = None,
) -> str:
    limits = limits or EvidenceLimits()
    parts = [
        "# Simulated user's private goal and answers (the agent saw only the messages the user sent)"
        if record.interactive else "# Task prompt given to the agent",
        prompt.strip(),
        "",
        "# SKILL.md that was active",
        skill_md.strip(),
        "",
        "# Run status",
        f"completed: {record.completed}" + (f"\nerror: {record.error}" if record.error else ""),
        f"started_at: {record.started_at} (the container's clock is UTC; 'today' for the agent is this date)",
        f"duration_seconds: {record.duration_seconds}",
        f"tool_calls: {len(record.tool_calls)}   bash_commands: {len(record.commands)}",
    ]
    if record.interactive:
        parts += [
            f"mode: interactive — a simulated user (an LLM given a persona and the answers below) "
            f"replied to the agent; user replies after the opening message: {record.user_turns}",
            f"ended_awaiting_input: {record.awaiting_input}",
        ]
    parts += [
        "",
        "# Trajectory (USER messages, agent messages, tool calls, and truncated tool outputs)",
    ]
    if record.trajectory_path and Path(record.trajectory_path).exists():
        parts.append(trajectory_evidence(Path(record.trajectory_path), limits))
    else:
        parts.append("(no trajectory available)")

    parts += [
        "",
        "# Final response from the agent",
        _clip(record.final_response or "(none)", limits.final_response_chars),
        "",
        "# Workspace changes vs. the starting repository",
        f"created:  {record.files_created}",
        f"modified: {record.files_modified}",
        f"deleted:  {record.files_deleted}",
    ]
    if record.diff_stats:
        s = record.diff_stats
        parts.append(f"diff stats: {s.files_changed} files, +{s.insertions} -{s.deletions}")
    if record.diff_patch_path and Path(record.diff_patch_path).exists():
        patch = Path(record.diff_patch_path).read_text()
        parts += ["", "## Diff", _clip(patch, limits.patch_chars) if patch.strip() else "(empty)"]
    return "\n".join(parts)
