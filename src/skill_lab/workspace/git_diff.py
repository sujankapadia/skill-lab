"""Classify workspace changes against the baseline commit using git on the host (§10)."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from skill_lab.models.run_record import DiffStats


@dataclass
class WorkspaceChanges:
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    stats: DiffStats = field(default_factory=lambda: DiffStats(0, 0, 0))
    patch: str = ""


def _run(workspace: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(
        ["git", "-C", str(workspace), *args],
        capture_output=True, text=True, check=True, env=env,
    ).stdout


def workspace_changes(workspace: Path) -> WorkspaceChanges:
    """Diff the workspace's working tree (including untracked files) against HEAD."""
    workspace = workspace.resolve()
    changes = WorkspaceChanges()

    for line in _run(workspace, "status", "--porcelain", "--untracked-files=all").splitlines():
        code, path = line[:2], line[3:]
        if code == "??" or "A" in code:
            changes.files_created.append(path)
        elif "D" in code:
            changes.files_deleted.append(path)
        else:
            changes.files_modified.append(path)
    for files in (changes.files_created, changes.files_modified, changes.files_deleted):
        files.sort()

    # Stage everything into a scratch index so untracked files show up in the
    # diff without touching the workspace's real index. Must be absolute:
    # relative GIT_INDEX_FILE paths resolve against the worktree.
    env = {**os.environ, "GIT_INDEX_FILE": str(workspace / ".git" / "skill-lab-index")}
    _run(workspace, "add", "-A", env=env)
    numstat = _run(workspace, "diff", "--cached", "--numstat", "HEAD", env=env)
    changes.patch = _run(workspace, "diff", "--cached", "--binary", "HEAD", env=env)

    insertions = deletions = 0
    for line in numstat.splitlines():
        ins, dels, _ = line.split("\t", 2)
        insertions += int(ins) if ins != "-" else 0
        deletions += int(dels) if dels != "-" else 0
    changes.stats = DiffStats(len(numstat.splitlines()), insertions, deletions)
    return changes
