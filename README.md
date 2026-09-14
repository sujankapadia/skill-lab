# Skill Lab

Run an agent skill many times against the same task via [Harbor](https://github.com/laude-institute/harbor),
collect what the agent did, and analyze variation across runs. See
`skill-lab-project.md` for the full plan.

## Status: Phase 0 (Harbor spike) — done

`src/skill_lab/spike.py` proves Harbor can produce the behavioral dataset we need.
Findings and answers to the open questions are in `docs/harbor-spike.md`.

## Prerequisites

- Docker
- `uv tool install harbor` (pinned at 0.23.0 during the spike)
- `ANTHROPIC_API_KEY` in the environment

## Run the spike

```bash
python3 src/skill_lab/spike.py \
  --skill ./examples/architecture-docs/architecture-documentation \
  --repo  ./examples/architecture-docs/repo \
  --prompt-file ./examples/architecture-docs/prompt.md \
  --attempts 3 --concurrency 3 --name spike-3 \
  --json .skill-lab/spike/spike-3/runs.json
```

Re-parse an existing job without re-running:

```bash
python3 src/skill_lab/spike.py --parse-only .skill-lab/spike/spike-3/harbor/spike-3
```

Output per trial: completion status, error, duration, tokens/cost, tool-call
sequence, final response, trajectory path, workspace path, files
created/modified/deleted, and git diff stats.
