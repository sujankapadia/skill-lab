"""Generate a Harbor task from an ExperimentConfig and run it via the Harbor CLI.

Everything Harbor-specific about *executing* an experiment lives here. See
docs/harbor-spike.md for why each piece is the way it is.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from skill_lab.models.experiment import ExperimentConfig, ExperimentPaths

REPO_IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", ".DS_Store"
)

# Paths the agent tends to fill with junk; skip them when Harbor tars /app.
WORKSPACE_EXCLUDES = ["node_modules", "__pycache__", ".pytest_cache", ".venv"]

DOCKERFILE = """\
FROM ubuntu:24.04

RUN apt-get update \\
    && apt-get install -y --no-install-recommends \\
        git python3 python3-pytest ca-certificates curl bash procps \\
    && rm -rf /var/lib/apt/lists/*

# Pre-install Claude Code so Harbor's per-trial agent setup is skipped: its
# install step is a no-op when `claude` is already on PATH. This layer sits
# before the repo copy so Docker caches it across fixtures.
ARG CLAUDE_CODE_VERSION={claude_code_version}
RUN curl -fsSL https://downloads.claude.ai/claude-code-releases/bootstrap.sh | bash -s -- $CLAUDE_CODE_VERSION \\
    && ln -s /root/.local/bin/claude /usr/local/bin/claude \\
    && claude --version

WORKDIR /app
COPY repo/ /app/

# Every trial container starts from this image, so this commit is the shared
# baseline that per-trial workspace diffs are computed against.
RUN git init -q \\
    && git config user.email "skill-lab@example.invalid" \\
    && git config user.name "Skill Lab" \\
    && git add -A \\
    && git commit -qm "baseline"
"""

TASK_TOML = """\
schema_version = "1.4"

[metadata]
generator = "skill-lab"

[agent]
timeout_sec = {agent_timeout}

[environment]
build_timeout_sec = 600.0

# Download the whole workspace (including its .git) after the agent finishes.
[[artifacts]]
source = "/app"
exclude = {excludes}
"""


class HarborRunner:
    def __init__(self, config: ExperimentConfig, paths: ExperimentPaths) -> None:
        self.config = config
        self.paths = paths

    def build_task(self) -> Path:
        task_dir = self.paths.task_dir
        if task_dir.exists():
            shutil.rmtree(task_dir)
        env_dir = task_dir / "environment"
        env_dir.mkdir(parents=True)

        shutil.copytree(self.config.repo, env_dir / "repo", ignore=REPO_IGNORE)
        (env_dir / "Dockerfile").write_text(
            DOCKERFILE.format(claude_code_version=self.config.claude_code_version)
        )
        (task_dir / "instruction.md").write_text(self.config.prompt.rstrip() + "\n")
        (task_dir / "task.toml").write_text(
            TASK_TOML.format(
                agent_timeout=self.config.agent_timeout_sec,
                excludes=json.dumps(WORKSPACE_EXCLUDES),
            )
        )
        # Harbor requires a tests dir even when verification is disabled.
        tests_dir = task_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "test.sh").write_text("#!/bin/bash\necho 0 > /logs/verifier/reward.txt\n")
        return task_dir

    def _env(self) -> dict[str, str]:
        """Environment for the harbor subprocess.

        "subscription": Harbor's Claude Code adapter drops ANTHROPIC_API_KEY when
        CLAUDE_FORCE_OAUTH is truthy and forwards CLAUDE_CODE_OAUTH_TOKEN (from
        `claude setup-token`) into the container, so the CLI bills the user's
        Claude subscription instead of API usage.
        """
        env = dict(os.environ)
        if self.config.auth == "subscription":
            if not env.get("CLAUDE_CODE_OAUTH_TOKEN"):
                sys.exit(
                    "subscription auth requested but CLAUDE_CODE_OAUTH_TOKEN is not set.\n"
                    "Run `claude setup-token` and export the token, or pass --auth api."
                )
            env["CLAUDE_FORCE_OAUTH"] = "1"
        else:
            env.pop("CLAUDE_FORCE_OAUTH", None)
        return env

    def command(self, job_name: str) -> list[str]:
        cmd = [
            "harbor", "run",
            "--path", str(self.paths.task_dir),
            "--agent", self.config.agent,
            "--skill", str(self.config.skill),
            "--n-attempts", str(self.config.attempts),
            "--n-concurrent", str(self.config.concurrency),
            "--disable-verification",
            "--jobs-dir", str(self.paths.harbor_jobs_dir),
            "--job-name", job_name,
        ]
        if self.config.model:
            cmd += ["--model", self.config.model]
        return cmd

    def run(self, job_name: str) -> Path:
        """Run the job; returns the Harbor job directory."""
        cmd = self.command(job_name)
        print("$", " ".join(cmd), f"  [auth: {self.config.auth}]", flush=True)
        subprocess.run(cmd, check=True, env=self._env())
        return self.paths.harbor_job_dir(job_name)
