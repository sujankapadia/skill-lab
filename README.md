# Skill Lab

Run an agent skill many times against the same task via [Harbor](https://github.com/laude-institute/harbor),
collect what the agent did, and analyze variation across runs. See
`skill-lab-project.md` for the full plan.

## Status

- **Phase 0 — Harbor spike: done.** Findings in `docs/harbor-spike.md`.
- **Phase 1 — normalize runs: done.** `skill-lab run` / `inspect` / `normalize`.
- **Phase 2 — per-run summaries: done.** `skill-lab summarize`.
- **Phase 3 — cross-run analysis: done.** `skill-lab analyze` → `analysis.json` + `report.md`; `run` does it automatically.
- **Phase 4 — compare skill versions: done.** `skill-lab compare v1 v2`.

## Prerequisites

- Docker
- `uv` (this project) and `uv tool install harbor` (pinned at 0.23.0 during the spike)
- A Claude subscription token: `claude setup-token`, exported as `CLAUDE_CODE_OAUTH_TOKEN`

## Usage

```bash
uv sync

# Run an experiment: N Claude Code trials of one skill against one repo + prompt,
# then summarize each run and analyze them together (pass --no-analyze to stop early).
uv run skill-lab run \
  --skill ./examples/architecture-docs/skills/v1/architecture-documentation \
  --repo  ./examples/architecture-docs/repo \
  --prompt-file ./examples/architecture-docs/prompt.md \
  --attempts 20 --concurrency 4 --name arch-v1

# Table of runs (time, tool calls, files changed, tokens, cost).
uv run skill-lab inspect arch-v1

# Full detail (tool-call sequence, final response, paths) for specific runs.
uv run skill-lab inspect arch-v1 --run 3 8

# Rebuild runs/ from the Harbor job without re-running the agent.
uv run skill-lab normalize arch-v1

# Write an LLM behavioral summary (summary.json) per run; `inspect --run N` shows it.
uv run skill-lab summarize arch-v1 --concurrency 3

# Cross-run analysis (summarizes any runs that lack a summary first).
uv run skill-lab analyze arch-v1

# Edit the skill, run it again under a new name, then compare observed behavior.
uv run skill-lab run --skill ./examples/architecture-docs/skills/v2/architecture-documentation \
  --repo ./examples/architecture-docs/repo --prompt-file ./examples/architecture-docs/prompt.md \
  --attempts 20 --name arch-v2
uv run skill-lab compare arch-v1 arch-v2      # -> .skill-lab/comparisons/arch-v1--arch-v2/report.md
```

`examples/architecture-docs/` holds the worked example: a fixture repo with
architecture notes split across a stale `docs/architecture.md`, an outdated
README section and accurate ADRs; `skills/v1` (the deliberately thin original)
and `skills/v2` (revised from the v1 analysis).

Experiments live under `.skill-lab/experiments/<name>/`:

```
experiment.yaml     # what was run: skill digest, repo commit, prompt, agent, Harbor version
task/               # generated Harbor task (Dockerfile bakes in the repo + Claude Code)
harbor/<name>/      # Harbor job: one trial dir per attempt (trajectory, workspace, result)
skill/              # snapshot of the skill directory as it was run
runs/NNN/           # run.json (RunRecord), diff.patch, diff-stat.json, summary.json
analysis.json       # clusters, recurring patterns/problems, outliers, strong runs, suggested changes
report.md           # the same, written for the skill author
```

## Tests

```bash
uv run pytest
```

## Billing

Rollouts and analysis calls run on your Claude subscription by default:

```bash
claude setup-token                                # one-time, prints a token
export CLAUDE_CODE_OAUTH_TOKEN=...                # put it in ~/.zshrc
```

Pass `--auth api` to bill `ANTHROPIC_API_KEY` instead.
