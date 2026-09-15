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
        git python3 python3-pytest ca-certificates curl bash procps {apt_packages} \\
    && rm -rf /var/lib/apt/lists/*

# Pre-install Claude Code so Harbor's per-trial agent setup is skipped: its
# install step is a no-op when `claude` is already on PATH. This layer sits
# before the repo copy so Docker caches it across fixtures.
ARG CLAUDE_CODE_VERSION={claude_code_version}
RUN curl -fsSL https://downloads.claude.ai/claude-code-releases/bootstrap.sh | bash -s -- $CLAUDE_CODE_VERSION \\
    && ln -s /root/.local/bin/claude /usr/local/bin/claude \\
    && claude --version

{interactive_layers}WORKDIR /app
COPY repo/ /app/
{project_skill_layer}
# Every trial container starts from this image, so this commit is the shared
# baseline that per-trial workspace diffs are computed against.
RUN git init -q \\
    && git config user.email "skill-lab@example.invalid" \\
    && git config user.name "Skill Lab" \\
    && git add -A \\
    && git commit -qm "baseline"
"""

# Interactive mode only. Harbor spawns the ACP target (claude-code-acp) from a
# setup exec that lacks the auth overlay, and the simulated user's shell has the
# OAuth token stripped by Claude Code; the container's PID 1 env (set from
# task.toml [environment.env]) is the one place it survives. This wrapper sits
# earlier on PATH than the npm-installed binary and re-injects it.
ACP_WRAPPER = """\
#!/usr/bin/env node
// Skill Lab wrapper around @zed-industries/claude-code-acp.
//
// Harbor "pins" whatever `command -v claude-code-acp` finds by rewriting
// /usr/local/bin/claude-code-acp to `exec node <that path>`, so this file must be
// JavaScript, and it must locate the real adapter through node_modules rather
// than PATH (which would resolve back to this wrapper or the pinned copy).
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

if (!process.env.CLAUDE_CODE_OAUTH_TOKEN) {
  try {
    const entry = fs.readFileSync("/proc/1/environ").toString("utf8").split("\\0")
      .find((kv) => kv.startsWith("CLAUDE_CODE_OAUTH_TOKEN="));
    if (entry) process.env.CLAUDE_CODE_OAUTH_TOKEN = entry.slice("CLAUDE_CODE_OAUTH_TOKEN=".length);
  } catch (_) {}
}

const roots = ["/usr/lib/node_modules", "/usr/local/lib/node_modules"];
for (const nvm of ["/root/.nvm/versions/node"]) {
  try { for (const v of fs.readdirSync(nvm)) roots.push(path.join(nvm, v, "lib", "node_modules")); } catch (_) {}
}
let entry = null;
for (const root of roots) {
  const pkgDir = path.join(root, "@zed-industries", "claude-code-acp");
  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(pkgDir, "package.json"), "utf8"));
    const bin = typeof pkg.bin === "string" ? pkg.bin : pkg.bin && pkg.bin["claude-code-acp"];
    if (bin) { entry = path.join(pkgDir, bin); break; }
  } catch (_) {}
}
if (!entry) { console.error("skill-lab acp wrapper: @zed-industries/claude-code-acp not found in " + roots.join(", ")); process.exit(127); }

const child = spawn(process.execPath, [entry, ...process.argv.slice(2)], { stdio: "inherit", env: process.env });
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) process.on(sig, () => child.kill(sig));
child.on("exit", (code, signal) => { if (signal) process.kill(process.pid, signal); else process.exit(code == null ? 1 : code); });
"""

# Versions Harbor 0.23.0 pins (harbor/bridges/acp.py ACPX_NPM_VERSION,
# harbor/agents/installed/claude_code.py CLAUDE_CODE_ACP_VERSION). Harbor still
# runs `npm install -g <pkg>@<version>` per trial, but with Node >= 20 and the
# same versions present that is seconds instead of a multi-minute nvm bootstrap.
ACPX_VERSION = "0.11.2"
CLAUDE_CODE_ACP_VERSION = "0.16.2"

INTERACTIVE_LAYERS = """\
# Interactive mode: Node 22 + the ACP bridge packages Harbor would otherwise
# install on every trial.
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \\
    && apt-get install -y --no-install-recommends nodejs \\
    && rm -rf /var/lib/apt/lists/* \\
    && npm install -g acpx@{acpx_version} @zed-industries/claude-code-acp@{acp_version}

# Interactive mode: re-inject the subscription token for the ACP target.
COPY claude-code-acp-wrapper /usr/local/sbin/claude-code-acp
RUN chmod +x /usr/local/sbin/claude-code-acp

"""

# Interactive mode: Harbor 0.23.0 does not register --skill for the ACP target
# (acp_install skips the step run() performs), so install it as a project skill,
# which Claude Code loads from the working directory in every mode.
PROJECT_SKILL_LAYER = """\
COPY skill/ /app/.claude/skills/{skill_name}/
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
        skill_name = self.config.skill.resolve().name
        if self.config.interactive:
            shutil.copytree(self.config.skill, env_dir / "skill", ignore=REPO_IGNORE)
            (env_dir / "claude-code-acp-wrapper").write_text(ACP_WRAPPER)
        (env_dir / "Dockerfile").write_text(
            DOCKERFILE.format(
                claude_code_version=self.config.claude_code_version,
                apt_packages=" ".join(self.config.apt_packages),
                interactive_layers=(
                    INTERACTIVE_LAYERS.format(acpx_version=ACPX_VERSION, acp_version=CLAUDE_CODE_ACP_VERSION)
                    if self.config.interactive else ""
                ),
                project_skill_layer=PROJECT_SKILL_LAYER.format(skill_name=skill_name) if self.config.interactive else "",
            )
        )
        # In interactive mode instruction.md is the simulated user's private
        # goal (Harbor hands it to the user agent, not the target), so it
        # carries the persona: how to open, and what to answer.
        instruction = self.config.persona if self.config.interactive else self.config.prompt
        if not instruction:
            raise ValueError("interactive mode requires a persona")
        (task_dir / "instruction.md").write_text(instruction.rstrip() + "\n")
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

    def _token_env_block(self) -> str:
        return (
            "\n[environment.env]\nCLAUDE_CODE_OAUTH_TOKEN = "
            + json.dumps(os.environ["CLAUDE_CODE_OAUTH_TOKEN"]) + "\n"
        )

    def _inject_token(self) -> None:
        """Interactive + subscription: put the token in the container env via
        task.toml (see ACP_WRAPPER). Scrubbed again by _scrub_token()."""
        toml = self.paths.task_dir / "task.toml"
        toml.write_text(toml.read_text() + self._token_env_block())

    def _scrub_token(self) -> None:
        toml = self.paths.task_dir / "task.toml"
        text = toml.read_text()
        marker = "\n[environment.env]\n"
        if marker in text:
            toml.write_text(text[: text.index(marker)])

    def command(self, job_name: str) -> list[str]:
        cmd = [
            "harbor", "run",
            "--path", str(self.paths.task_dir),
            "--agent", self.config.agent,
            "--n-attempts", str(self.config.attempts),
            "--n-concurrent", str(self.config.concurrency),
            "--disable-verification",
            "--jobs-dir", str(self.paths.harbor_jobs_dir),
            "--job-name", job_name,
        ]
        if self.config.model:
            cmd += ["--model", self.config.model]
        if not self.config.interactive:
            cmd += ["--skill", str(self.config.skill)]
        else:
            cmd += ["--bridge", "acp", "--user-agent", "claude-code"]
            if self.config.user_model:
                cmd += ["--user-model", self.config.user_model]
        return cmd

    def run(self, job_name: str) -> Path:
        """Run the job; returns the Harbor job directory."""
        cmd = self.command(job_name)
        env = self._env()
        inject = self.config.interactive and self.config.auth == "subscription"
        if inject:
            self._inject_token()
        print("$", " ".join(cmd), f"  [auth: {self.config.auth}{', interactive' if self.config.interactive else ''}]", flush=True)
        try:
            subprocess.run(cmd, check=True, env=env)
        finally:
            if inject:
                self._scrub_token()
        return self.paths.harbor_job_dir(job_name)
