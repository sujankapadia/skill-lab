"""Convert a native Claude Code session log (.jsonl) into the ATIF-shaped dict
the rest of Skill Lab reads.

Harbor does this itself for headless trials (agent/trajectory.json) but not for
ACP/simulated-user trials, where only the raw session survives at
agent/sessions/projects/<cwd-slug>/<session-id>.jsonl. Only the fields we use
are produced: agent steps with text, tool calls, observations and token
metrics; user steps with text.
"""

from __future__ import annotations

import json
from pathlib import Path


def find_session_files(agent_dir: Path) -> list[Path]:
    root = agent_dir / "sessions" / "projects"
    if not root.is_dir():
        return []
    return sorted(
        p for p in root.rglob("*.jsonl") if "subagents" not in p.parts and "memory" not in p.parts
    )


def _blocks(message: dict) -> list[dict]:
    content = message.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in (content or []) if isinstance(b, dict)]


def convert_session(paths: list[Path]) -> dict:
    events = []
    for p in paths:
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    events.sort(key=lambda e: e.get("timestamp") or "")

    steps: list[dict] = []
    call_step: dict[str, dict] = {}      # tool_use_id -> step
    seen_usage: set[str] = set()
    agent_version = None
    model = None
    totals = {"prompt": 0, "completion": 0, "cached": 0}

    for e in events:
        kind = e.get("type")
        msg = e.get("message") or {}
        if kind == "assistant":
            agent_version = agent_version or e.get("version")
            model = model or msg.get("model")
            msg_id = msg.get("id")
            # Claude Code writes one line per content block; merge blocks that
            # share a message id into a single step.
            if steps and steps[-1]["source"] == "agent" and msg_id and steps[-1].get("_msg_id") == msg_id:
                step = steps[-1]
            else:
                step = {
                    "step_id": len(steps) + 1, "timestamp": e.get("timestamp"), "source": "agent",
                    "message": "", "model_name": msg.get("model"), "tool_calls": [],
                    "observation": {"results": []}, "metrics": None, "_msg_id": msg_id,
                }
                steps.append(step)
            for b in _blocks(msg):
                if b.get("type") == "text":
                    step["message"] = (step["message"] + "\n" + b.get("text", "")).strip()
                elif b.get("type") == "tool_use":
                    call_id = str(b.get("id"))
                    # Under the ACP bridge Claude Code's tools appear as mcp__acp__<Name>.
                    name = str(b.get("name") or "?").removeprefix("mcp__acp__")
                    step["tool_calls"].append({
                        "tool_call_id": call_id, "function_name": name, "arguments": b.get("input") or {},
                    })
                    call_step[call_id] = step
            usage = msg.get("usage")
            if usage and msg_id and msg_id not in seen_usage:
                seen_usage.add(msg_id)
                prompt = (usage.get("input_tokens") or 0) + (usage.get("cache_creation_input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
                step["metrics"] = {
                    "prompt_tokens": prompt,
                    "completion_tokens": usage.get("output_tokens") or 0,
                    "cached_tokens": usage.get("cache_read_input_tokens") or 0,
                }
                totals["prompt"] += prompt
                totals["completion"] += usage.get("output_tokens") or 0
                totals["cached"] += usage.get("cache_read_input_tokens") or 0
        elif kind == "user":
            texts = []
            for b in _blocks(msg):
                if b.get("type") == "tool_result":
                    step = call_step.get(str(b.get("tool_use_id")))
                    if step is None:
                        continue
                    content = b.get("content")
                    if isinstance(content, list):
                        content = "\n".join(x.get("text", "") for x in content if isinstance(x, dict))
                    step["observation"]["results"].append({
                        "source_call_id": b.get("tool_use_id"),
                        "content": content or "",
                        "extra": {"tool_result_metadata": {"tool_use_result": e.get("toolUseResult")}},
                    })
                elif b.get("type") == "text" and b.get("text", "").strip():
                    texts.append(b["text"].strip())
            if texts:
                steps.append({
                    "step_id": len(steps) + 1, "timestamp": e.get("timestamp"), "source": "user",
                    "message": "\n".join(texts),
                })

    for s in steps:
        s.pop("_msg_id", None)
        if s["source"] == "agent" and not s["observation"]["results"]:
            s["observation"] = None

    return {
        "schema_version": "skill-lab-native-v1",
        "agent": {"name": "claude-code", "version": agent_version, "model_name": model},
        "steps": steps,
        "final_metrics": {
            "total_prompt_tokens": totals["prompt"],
            "total_completion_tokens": totals["completion"],
            "total_cached_tokens": totals["cached"],
            "total_steps": len(steps),
        },
    }
