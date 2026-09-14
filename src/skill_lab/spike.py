"""Phase 0 Harbor spike.

Takes a local skill directory, a local repository, a prompt and an attempt
count; runs Claude Code N times through upstream Harbor against clean copies
of the repository; then prints what each trial did.

No LLM analysis, no framework. The point is to prove Harbor can reliably
produce the behavioral dataset described in skill-lab-project.md.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", ".pytest_cache", ".venv", "node_modules", ".DS_Store"
)

# Paths the agent tends to fill with junk; skip them when Harbor tars /app.
WORKSPACE_EXCLUDES = ["node_modules", "__pycache__", ".pytest_cache", ".venv"]

DOCKERFILE = """\
FROM ubuntu:24.04

RUN apt-get update \\
    && apt-get install -y --no-install-recommends git python3 python3-pytest ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

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
generator = "skill-lab-spike"

[agent]
timeout_sec = {agent_timeout}

[environment]
build_timeout_sec = 600.0

# Download the whole workspace (including its .git) after the agent finishes.
[[artifacts]]
source = "/app"
exclude = {excludes}
"""


# --------------------------------------------------------------------------- #
# Task generation
# --------------------------------------------------------------------------- #


def build_task(task_dir: Path, repo: Path, prompt: str, agent_timeout: float) -> None:
    if task_dir.exists():
        shutil.rmtree(task_dir)
    env_dir = task_dir / "environment"
    env_dir.mkdir(parents=True)

    shutil.copytree(repo, env_dir / "repo", ignore=REPO_IGNORE)
    (env_dir / "Dockerfile").write_text(DOCKERFILE)
    (task_dir / "instruction.md").write_text(prompt.rstrip() + "\n")
    (task_dir / "task.toml").write_text(
        TASK_TOML.format(agent_timeout=agent_timeout, excludes=json.dumps(WORKSPACE_EXCLUDES))
    )
    # Harbor requires a tests dir even when verification is disabled.
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test.sh").write_text("#!/bin/bash\necho 0 > /logs/verifier/reward.txt\n")


# --------------------------------------------------------------------------- #
# Harbor invocation
# --------------------------------------------------------------------------- #


def run_harbor(
    task_dir: Path,
    skill: Path,
    jobs_dir: Path,
    job_name: str,
    agent: str,
    model: str | None,
    attempts: int,
    concurrency: int,
) -> Path:
    cmd = [
        "harbor", "run",
        "--path", str(task_dir),
        "--agent", agent,
        "--skill", str(skill),
        "--n-attempts", str(attempts),
        "--n-concurrent", str(concurrency),
        "--disable-verification",
        "--jobs-dir", str(jobs_dir),
        "--job-name", job_name,
    ]
    if model:
        cmd += ["--model", model]
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    return jobs_dir / job_name


# --------------------------------------------------------------------------- #
# Result parsing
# --------------------------------------------------------------------------- #


def _git(workspace: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(workspace), *args], capture_output=True, text=True, check=True
    ).stdout


def workspace_changes(workspace: Path) -> dict:
    """Classify changes against the baseline commit using git on the host."""
    created, modified, deleted = [], [], []
    for line in _git(workspace, "status", "--porcelain", "--untracked-files=all").splitlines():
        code, path = line[:2], line[3:]
        if code == "??" or "A" in code:
            created.append(path)
        elif "D" in code:
            deleted.append(path)
        else:
            modified.append(path)

    # Stage everything (in a scratch index) so untracked files show up in the diff.
    workspace = workspace.resolve()
    env = {**os.environ, "GIT_INDEX_FILE": str(workspace / ".git" / "skill-lab-index")}
    subprocess.run(["git", "-C", str(workspace), "add", "-A"], env=env, check=True, capture_output=True)
    numstat = subprocess.run(
        ["git", "-C", str(workspace), "diff", "--cached", "--numstat", "HEAD"],
        env=env, capture_output=True, text=True, check=True,
    ).stdout
    patch = subprocess.run(
        ["git", "-C", str(workspace), "diff", "--cached", "--binary", "HEAD"],
        env=env, capture_output=True, text=True, check=True,
    ).stdout

    insertions = deletions = 0
    for line in numstat.splitlines():
        ins, dels, _ = line.split("\t", 2)
        insertions += int(ins) if ins != "-" else 0
        deletions += int(dels) if dels != "-" else 0

    return {
        "files_created": sorted(created),
        "files_modified": sorted(modified),
        "files_deleted": sorted(deleted),
        "diff_stats": {
            "files_changed": len(numstat.splitlines()),
            "insertions": insertions,
            "deletions": deletions,
        },
        "patch": patch,
    }


def _text_of(message) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        return "\n".join(p.get("text", "") for p in message if isinstance(p, dict) and p.get("type") == "text")
    return ""


def trajectory_facts(path: Path) -> dict:
    traj = json.loads(path.read_text())
    steps = traj.get("steps", [])
    tool_calls = []
    final_response = None
    for step in steps:
        if step.get("source") != "agent":
            continue
        for call in step.get("tool_calls") or []:
            tool_calls.append(call.get("function_name"))
        if _text_of(step.get("message")).strip():
            final_response = _text_of(step["message"]).strip()
    metrics = traj.get("final_metrics") or {}
    return {
        "schema_version": traj.get("schema_version"),
        "n_steps": len(steps),
        "tool_calls": tool_calls,
        "final_response": final_response,
        "final_metrics": metrics,
    }


def _seconds(timing: dict | None) -> float | None:
    if not timing or not timing.get("started_at") or not timing.get("finished_at"):
        return None
    start = datetime.fromisoformat(timing["started_at"])
    end = datetime.fromisoformat(timing["finished_at"])
    return (end - start).total_seconds()


def parse_trial(trial_dir: Path) -> dict:
    result = json.loads((trial_dir / "result.json").read_text())
    record: dict = {
        "trial_name": result.get("trial_name"),
        "trial_path": str(trial_dir),
        "completed": result.get("exception_info") is None,
        "error": (result.get("exception_info") or {}).get("exception_message"),
        "duration_seconds": _seconds(result.get("agent_execution")),
        "agent_version": (result.get("agent_info") or {}).get("version"),
        "model": ((result.get("agent_info") or {}).get("model_info") or {}).get("name"),
    }
    agent_result = result.get("agent_result") or {}
    record.update(
        input_tokens=agent_result.get("n_input_tokens"),
        cache_tokens=agent_result.get("n_cache_tokens"),
        output_tokens=agent_result.get("n_output_tokens"),
        cost_usd=agent_result.get("cost_usd"),
    )

    trajectory = trial_dir / "agent" / "trajectory.json"
    record["trajectory_path"] = str(trajectory) if trajectory.exists() else None
    if trajectory.exists():
        record["trajectory"] = trajectory_facts(trajectory)

    workspace = trial_dir / "artifacts" / "app"
    record["workspace_path"] = str(workspace) if workspace.exists() else None
    if (workspace / ".git").exists():
        record["workspace"] = workspace_changes(workspace)
    return record


def parse_job(job_dir: Path) -> list[dict]:
    trials = sorted(p.parent for p in job_dir.glob("*/result.json"))
    return [parse_trial(t) for t in trials]


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #


def print_report(job_dir: Path, records: list[dict]) -> None:
    # Harbor records resolved skills (name = directory name, sha256 digest of
    # contents) in each trial's lock.json; they are identical across trials.
    for lock in sorted(job_dir.glob("*/lock.json"))[:1]:
        for skill in json.loads(lock.read_text()).get("skills") or []:
            print(f"Skill: {skill.get('name')}  digest: {skill.get('digest')}  source: {skill.get('source')}")
    print(f"Harbor job: {job_dir}")
    print(f"{len([r for r in records if r['completed']])}/{len(records)} trials completed\n")

    print(f"{'RUN':<4} {'OK':<3} {'TIME':>6} {'TOOLS':>5} {'FILES':>5} {'+LINES':>6} {'-LINES':>6} {'IN_TOK':>8} {'OUT_TOK':>8} {'COST':>7}")
    for i, r in enumerate(records, 1):
        ws = r.get("workspace", {})
        stats = ws.get("diff_stats", {})
        n_tools = len(r.get("trajectory", {}).get("tool_calls", []))
        dur = f"{r['duration_seconds']:.0f}s" if r["duration_seconds"] is not None else "-"
        cost = f"${r['cost_usd']:.2f}" if r.get("cost_usd") is not None else "-"
        print(
            f"{i:<4} {'y' if r['completed'] else 'N':<3} {dur:>6} {n_tools:>5} "
            f"{stats.get('files_changed', '-'):>5} {stats.get('insertions', '-'):>6} {stats.get('deletions', '-'):>6} "
            f"{r.get('input_tokens') if r.get('input_tokens') is not None else '-':>8} "
            f"{r.get('output_tokens') if r.get('output_tokens') is not None else '-':>8} {cost:>7}"
        )

    for i, r in enumerate(records, 1):
        print(f"\n=== Run {i}: {r['trial_name']} ===")
        print(f"completed:   {r['completed']}" + (f"  error: {r['error']}" if r["error"] else ""))
        print(f"trajectory:  {r['trajectory_path']}")
        print(f"workspace:   {r['workspace_path']}")
        ws = r.get("workspace")
        if ws:
            print(f"created:     {ws['files_created']}")
            print(f"modified:    {ws['files_modified']}")
            print(f"deleted:     {ws['files_deleted']}")
            print(f"diff stats:  {ws['diff_stats']}")
        tr = r.get("trajectory")
        if tr:
            print(f"tool calls:  {len(tr['tool_calls'])} — {', '.join(tr['tool_calls'][:12])}{' …' if len(tr['tool_calls']) > 12 else ''}")
            resp = (tr.get("final_response") or "").replace("\n", " ")
            print(f"final:       {resp[:300]}{'…' if len(resp) > 300 else ''}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skill", type=Path, help="Local skill directory containing SKILL.md")
    ap.add_argument("--repo", type=Path, help="Local repository fixture")
    ap.add_argument("--prompt", help="Task prompt text")
    ap.add_argument("--prompt-file", type=Path, help="File containing the task prompt")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--agent", default="claude-code")
    ap.add_argument("--model", default="anthropic/claude-sonnet-5")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--agent-timeout", type=float, default=900.0, help="Per-trial agent timeout in seconds")
    ap.add_argument("--name", help="Experiment/job name (default: timestamp)")
    ap.add_argument("--output", type=Path, default=Path(".skill-lab/spike"))
    ap.add_argument("--parse-only", type=Path, metavar="JOB_DIR", help="Skip execution; parse an existing Harbor job dir")
    ap.add_argument("--json", type=Path, help="Also write parsed records to this JSON file")
    args = ap.parse_args(argv)

    if args.parse_only:
        job_dir = args.parse_only
    else:
        if not (args.skill and args.repo and (args.prompt or args.prompt_file)):
            ap.error("--skill, --repo and --prompt/--prompt-file are required unless --parse-only is used")
        prompt = args.prompt_file.read_text() if args.prompt_file else args.prompt
        name = args.name or datetime.now().strftime("spike-%Y%m%d-%H%M%S")
        exp_dir = args.output / name
        task_dir = exp_dir / "task"
        build_task(task_dir, args.repo, prompt, args.agent_timeout)
        job_dir = run_harbor(
            task_dir, args.skill, exp_dir / "harbor", name,
            args.agent, args.model, args.attempts, args.concurrency,
        )

    records = parse_job(job_dir)
    print_report(job_dir, records)
    if args.json:
        slim = [{k: v for k, v in r.items()} for r in records]
        for r in slim:
            if "workspace" in r:
                r["workspace"] = {k: v for k, v in r["workspace"].items() if k != "patch"}
        args.json.write_text(json.dumps(slim, indent=2))
        print(f"\nwrote {args.json}")
    return 0 if records and all(r["completed"] for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
