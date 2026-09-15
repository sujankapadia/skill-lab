# Skill Lab

**You can't tell how good an agent skill is by reading it, or by trying it once.**

A `SKILL.md` is a prompt, and an agent follows it non-deterministically. The
gaps that matter aren't syntax errors — they're the questions your instructions
never answered, which the agent silently answers differently every time. You
won't see them in a single run, because a single run looks fine.

Skill Lab runs your skill 20–50 times against the same task in identical
containers, then tells you what actually varied.

## Why you should care

A real example from this repo. A four-step documentation skill, run 20 times on
one repository, looked perfectly reasonable — every run produced a decent
document. But the repo also had a stale architecture blurb in its README, and
the skill never said what to do about it:

```
Behavior                                    v1       v2
Updated the contradicting README section   10/20   20/20
Read CONTRIBUTING.md for doc conventions    0/20    17/20
Document well over the length guidance     12/20     0/20
Modified source code (it shouldn't)          0/20     0/20
```

Ten runs fixed the README, ten left the repository contradicting itself — a
coin flip nobody would ever notice one run at a time. Skill Lab found it,
traced it to the missing instruction, and suggested the sentence to add. `v2`
is that sentence. The right column is the same skill after the edit.

## Why you should use it

- **It finds ambiguity, not bugs.** Where your skill is silent, the agent
  improvises. Frequencies across many runs make that visible.
- **Evidence, not vibes.** Every finding cites the runs it rests on; `inspect
  --run 7` shows you that run's whole trajectory and diff.
- **It closes the loop.** Edit the skill, re-run, and `compare` tells you
  whether behavior actually changed — and what new behavior the edit introduced.
- **It is not an eval harness.** No expected outputs, no pass/fail, no graders
  to write. You supply a skill, a repo, and a prompt.
- **It's cheap.** ~20 minutes and $0 for 20 runs on a Claude subscription.

It works on skills that ask the user questions, too: a simulated user answers
from a persona file, so all 20 runs get identical answers and the only thing
varying is the skill.

## How it works

Your skill + a repo fixture + a prompt → [Harbor](https://github.com/laude-institute/harbor)
runs N isolated trials → each run's trajectory and workspace diff are normalized
→ an LLM summarizes each run → a second pass finds clusters, recurring problems,
outliers, strong runs, and suggested `SKILL.md` edits → `report.md`.

Harbor is the execution substrate (containers, agent installation, trajectories);
Skill Lab is the behavior-analysis layer on top. `skill-lab-project.md` is the
original design doc.

## Status

Complete and used end to end on real skills. Commands: `run`, `inspect`,
`normalize`, `summarize`, `analyze`, `compare`.

- Harbor integration findings (verified, not documentation-derived): `docs/harbor-spike.md`
- Worked example with real reports: `examples/architecture-docs/`
- Interactive-skill example: `examples/sow-draft/`

Not built yet: hierarchical summarization for experiments beyond ~50 runs,
agents other than Claude Code, deterministic checks (tests pass, protected files
touched).

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

# Faster, shallower summaries (~3 min vs ~8 min per 20 runs). Haiku gets the
# facts right but is weaker at noticing what the agent *didn't* do: in a test it
# missed 1 of 2 runs that skipped an instructed file, so keep sonnet for the
# analysis you act on.
uv run skill-lab summarize arch-v1 --model haiku

# Edit the skill, run it again under a new name, then compare observed behavior.
uv run skill-lab run --skill ./examples/architecture-docs/skills/v2/architecture-documentation \
  --repo ./examples/architecture-docs/repo --prompt-file ./examples/architecture-docs/prompt.md \
  --attempts 20 --name arch-v2
uv run skill-lab compare arch-v1 arch-v2      # -> .skill-lab/comparisons/arch-v1--arch-v2/report.md
```

`examples/architecture-docs/` holds the worked example: a fixture repo with
architecture notes split across a stale `docs/architecture.md`, an outdated
README section and accurate ADRs; `skills/v1` (the deliberately thin original)
and `skills/v2` (revised from the v1 analysis); and `results/` with the actual
v1 report, v2 report and v1→v2 comparison from 20-run experiments. Headline:
v1 split 10/20 on whether to reconcile the README's stale architecture section;
v2, which tells the agent to, went 20/20 — and surfaced a new 3/20 miss on
reading CONTRIBUTING.md.

## MVP definition of done (§22 of the plan)

| # | Criterion | Status |
|---|---|---|
| 1–4 | Real SKILL.md, realistic repo and prompt, 20 Claude Code runs via Harbor | done (`inv-v1`) |
| 5 | Each run starts from the same repo state | baseline commit baked into the image; verified |
| 6 | Trajectory + final workspace collected | ATIF + `/app` artifact per trial |
| 7 | Each run summarized automatically | `summarize` |
| 8 | Multiple behavioral patterns identified | 2 strategies (10/10) in v1 |
| 9 | A recurring problem surfaced | README left contradictory in 10/20 |
| 10 | A strong run identified with reasons | yes (e.g. #4, #7: flagged the inconsistency instead of guessing) |
| 11 | A SKILL.md improvement tied to evidence | yes; became v2 |
| 12–14 | Edit, rerun 20×, compare | `inv-v2` + `compare`: 10/20 → 20/20 |

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

## Interactive skills

Skills that ask the user questions can't run headless (Claude Code has no
`AskUserQuestion` in `-p` mode; the run just ends). `--interactive` makes each
trial a conversation: a second Claude Code instance plays the user, following a
persona file that holds its goal and the answers to give, so every run gets the
same answers. Still billed to the subscription.

```bash
uv run skill-lab run --interactive \
  --skill ./path/to/sow-draft --repo ./examples/sow-draft/workspace \
  --persona-file ./examples/sow-draft/persona-acme.md --apt python3-docx \
  --attempts 20 --name sow-v1
```

`inspect` gains REPLIES (messages the simulated user sent) and WAITING (the run
ended on an unanswered question); the evidence the summarizer sees is the full
transcript. `--apt` adds packages the skill needs in the image.

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
