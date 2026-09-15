"""Experiment configuration, manifest (experiment.yaml) and directory layout (§7, §8)."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

MANIFEST_FILENAME = "experiment.yaml"


@dataclass
class ExperimentConfig:
    """What the user asked for. Paths are as given on the command line."""

    id: str
    skill: Path
    repo: Path
    prompt: str
    attempts: int
    agent: str = "claude-code"
    model: str | None = "anthropic/claude-sonnet-5"
    concurrency: int = 4
    agent_timeout_sec: float = 900.0
    auth: str = "subscription"
    claude_code_version: str = "latest"
    apt_packages: list[str] = field(default_factory=list)
    # Interactive mode: a second agent plays the user, driven by `persona`
    # (its private goal and the answers it should give). See docs/harbor-spike.md.
    interactive: bool = False
    persona: str | None = None
    user_model: str | None = "anthropic/claude-sonnet-5"


@dataclass
class ExperimentPaths:
    """Directory layout of one experiment.

    <root>/
    ├── experiment.yaml
    ├── skill/           # snapshot of the skill directory as run
    ├── task/            # generated Harbor task
    ├── harbor/<id>/     # Harbor job output (trials live here; never copied)
    ├── runs/NNN/        # run.json, diff.patch, diff-stat.json
    ├── analysis.json    # Phase 3
    └── report.md        # Phase 3
    """

    root: Path

    @property
    def manifest(self) -> Path:
        return self.root / MANIFEST_FILENAME

    @property
    def skill_dir(self) -> Path:
        return self.root / "skill"

    @property
    def skill_md(self) -> Path:
        return self.skill_dir / "SKILL.md"

    @property
    def task_dir(self) -> Path:
        return self.root / "task"

    @property
    def harbor_jobs_dir(self) -> Path:
        return self.root / "harbor"

    def harbor_job_dir(self, job_name: str) -> Path:
        return self.harbor_jobs_dir / job_name

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"

    def run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    @property
    def analysis(self) -> Path:
        return self.root / "analysis.json"

    @property
    def report(self) -> Path:
        return self.root / "report.md"


@dataclass
class Manifest:
    """Persisted record of exactly what was run. Written before Harbor starts."""

    id: str
    created_at: str
    skill: dict
    repository: dict
    agent: dict
    prompt: dict
    execution: dict
    harbor: dict = field(default_factory=dict)
    environment: dict = field(default_factory=dict)

    def save(self, path: Path) -> None:
        path.write_text(yaml.safe_dump(self.__dict__, sort_keys=False))

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        return cls(**yaml.safe_load(path.read_text()))


REPO_DIGEST_IGNORE = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", ".DS_Store"}


def compute_skill_digest(skill_dir: Path, ignore: set[str] = frozenset()) -> str:
    """Same algorithm as harbor.skills.compute_skill_digest, so the value here
    matches the one Harbor writes to each trial's lock.json. With `ignore`, also
    used for the repository fixture (which is why paths under ignored
    directories are skipped rather than hashed)."""
    hasher = hashlib.sha256()
    for file_path in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
        rel = file_path.relative_to(skill_dir)
        if ignore and (set(rel.parts) & ignore):
            continue
        hasher.update(rel.as_posix().encode())
        hasher.update(b"\0")
        hasher.update(hashlib.sha256(file_path.read_bytes()).hexdigest().encode())
        hasher.update(b"\0")
    return f"sha256:{hasher.hexdigest()}"


def _git_commit(path: Path) -> dict:
    """Commit (and dirty flag) of the git repo containing `path`, if any."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain", "--", "."],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"git_commit": None, "git_dirty": None}
    return {"git_commit": commit, "git_dirty": dirty}


def _harbor_version() -> str | None:
    try:
        return subprocess.run(
            ["harbor", "--version"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def build_manifest(config: ExperimentConfig, job_name: str) -> Manifest:
    return Manifest(
        id=config.id,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        skill={
            "path": str(config.skill),
            "name": config.skill.resolve().name,
            "digest": compute_skill_digest(config.skill),
        },
        repository={
            "source": str(config.repo),
            "digest": compute_skill_digest(config.repo, REPO_DIGEST_IGNORE),
            **_git_commit(config.repo),
        },
        agent={
            "name": config.agent,
            "model": config.model,
            "auth": config.auth,
            "claude_code_version": config.claude_code_version,
            "interactive": config.interactive,
            "user_model": config.user_model if config.interactive else None,
        },
        prompt={
            "text": config.prompt,
            "persona": config.persona,
            "persona_digest": (
                "sha256:" + hashlib.sha256(config.persona.encode()).hexdigest() if config.persona else None
            ),
        },
        environment={"apt_packages": list(config.apt_packages)},
        execution={
            "attempts": config.attempts,
            "concurrency": config.concurrency,
            "agent_timeout_sec": config.agent_timeout_sec,
        },
        harbor={"version": _harbor_version(), "job_name": job_name},
    )
