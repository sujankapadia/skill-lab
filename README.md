# Skill Lab

Run an agent skill many times against the same task via [Harbor](https://github.com/laude-institute/harbor),
collect what the agent did, and analyze variation across runs. See
`skill-lab-project.md` for the full plan.

## Status

- **Phase 0 — Harbor spike: done.** Findings in `docs/harbor-spike.md`.
- **Phase 1 — normalize runs: done.** `skill-lab run` / `inspect` / `normalize`.
- Phase 2 (per-run summaries), 3 (cross-run analysis), 4 (compare): next.

## Prerequisites

- Docker
- `uv` (this project) and `uv tool install harbor` (pinned at 0.23.0 during the spike)
- A Claude subscription token: `claude setup-token`, exported as `CLAUDE_CODE_OAUTH_TOKEN`

## Usage

```bash
uv sync

# Run an experiment: N Claude Code trials of one skill against one repo + prompt.
uv run skill-lab run \
  --skill ./examples/architecture-docs/architecture-documentation \
  --repo  ./examples/architecture-docs/repo \
  --prompt-file ./examples/architecture-docs/prompt.md \
  --attempts 20 --concurrency 4 --name arch-v1

# Table of runs (time, tool calls, files changed, tokens, cost).
uv run skill-lab inspect arch-v1

# Full detail (tool-call sequence, final response, paths) for specific runs.
uv run skill-lab inspect arch-v1 --run 3 8

# Rebuild runs/ from the Harbor job without re-running the agent.
uv run skill-lab normalize arch-v1
```

Experiments live under `.skill-lab/experiments/<name>/`:

```
experiment.yaml     # what was run: skill digest, repo commit, prompt, agent, Harbor version
task/               # generated Harbor task (Dockerfile bakes in the repo + Claude Code)
harbor/<name>/      # Harbor job: one trial dir per attempt (trajectory, workspace, result)
runs/NNN/           # normalized RunRecord (run.json), diff.patch, diff-stat.json
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
