"""Total Claude Code token usage from local session logs.

`skill-lab usage <experiment>` reports what one experiment consumed. This
reports what *everything* on this machine consumed, which is the only view
that includes the `claude -p` analysis calls (they land in their own project
bucket) and lets you compare Skill Lab against your other work.

Source is `~/.claude/projects/**/*.jsonl` — the same local session history
Claude Code's own `/usage` reads. Two things it therefore cannot see:

- other devices, claude.ai, and Cowork, which share the same plan allowance;
- Skill Lab's own rollouts, which run inside containers and write their
  session files under the experiment directory, not `~/.claude`.

So treat it as a way to compare projects, not as your true plan total.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

SESSIONS_ROOT = Path.home() / ".claude" / "projects"

# Rough API price shape, used only to rank projects against each other:
# cache writes cost more than fresh input, cache reads much less, output most.
CACHE_WRITE_WEIGHT = 1.25
CACHE_READ_WEIGHT = 0.1
OUTPUT_WEIGHT = 5.0


@dataclass
class Totals:
    fresh: int = 0
    cache_write: int = 0
    cache_read: int = 0
    output: int = 0

    def add(self, usage: dict) -> None:
        self.fresh += usage.get("input_tokens") or 0
        self.cache_write += usage.get("cache_creation_input_tokens") or 0
        self.cache_read += usage.get("cache_read_input_tokens") or 0
        self.output += usage.get("output_tokens") or 0

    @property
    def weighted(self) -> float:
        return (
            self.fresh
            + CACHE_WRITE_WEIGHT * self.cache_write
            + CACHE_READ_WEIGHT * self.cache_read
            + OUTPUT_WEIGHT * self.output
        )


@dataclass
class LocalUsage:
    hours: float
    by_model: dict[str, Totals] = field(default_factory=lambda: defaultdict(Totals))
    by_project: dict[str, Totals] = field(default_factory=lambda: defaultdict(Totals))

    @property
    def total(self) -> Totals:
        out = Totals()
        for t in self.by_model.values():
            out.fresh += t.fresh
            out.cache_write += t.cache_write
            out.cache_read += t.cache_read
            out.output += t.output
        return out


def collect(hours: float = 24, root: Path = SESSIONS_ROOT) -> LocalUsage:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    usage = LocalUsage(hours=hours)
    if not root.is_dir():
        return usage

    for path in root.rglob("*.jsonl"):
        try:
            if path.stat().st_mtime < cutoff.timestamp():
                continue                       # cheap prefilter; thousands of files
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        project = path.parent.name
        seen: set[str] = set()                 # one line per content block; count each message once
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):      # valid JSON, but not an event object
                continue
            message = event.get("message")
            if not isinstance(message, dict):
                continue
            u = message.get("usage")
            when = _parsed(event.get("timestamp"))
            if not isinstance(u, dict) or when is None or when < cutoff:
                continue
            message_id = message.get("id")
            if message_id:
                if message_id in seen:
                    continue
                seen.add(message_id)
            usage.by_model[message.get("model") or "unknown"].add(u)
            usage.by_project[project].add(u)
    return usage


def _parsed(timestamp) -> datetime | None:
    if not isinstance(timestamp, str):
        return None
    try:
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def render(usage: LocalUsage, top: int = 12) -> str:
    lines = [
        f"Claude Code local sessions, last {usage.hours:g}h",
        "(excludes other devices, claude.ai, and Skill Lab's own containerized rollouts)",
        "",
        f"{'model':<28}{'fresh in':>12}{'cache write':>13}{'cache read':>14}{'output':>11}",
    ]
    for model, t in sorted(usage.by_model.items(), key=lambda kv: -kv[1].weighted):
        lines.append(f"{model:<28}{t.fresh:>12,}{t.cache_write:>13,}{t.cache_read:>14,}{t.output:>11,}")
    tot = usage.total
    lines.append(f"{'TOTAL':<28}{tot.fresh:>12,}{tot.cache_write:>13,}{tot.cache_read:>14,}{tot.output:>11,}")

    total_weight = sum(t.weighted for t in usage.by_project.values()) or 1
    lines += [
        "",
        f"weighted share by project (fresh + {CACHE_WRITE_WEIGHT}x cache write "
        f"+ {CACHE_READ_WEIGHT}x cache read + {OUTPUT_WEIGHT}x output):",
    ]
    for project, t in sorted(usage.by_project.items(), key=lambda kv: -kv[1].weighted)[:top]:
        lines.append(f"  {t.weighted / total_weight * 100:>5.1f}%  {t.weighted:>13,.0f}  {project}")
    return "\n".join(lines)
