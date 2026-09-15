# Skill Lab

**You can't tell how good an agent skill is by reading it, or by trying it once.**

A `SKILL.md` is a prompt, and an agent follows it non-deterministically. The
gaps that matter aren't syntax errors — they're the questions your instructions
never answered, which the agent silently answers differently every time. You
won't see them in a single run, because a single run looks fine.

Skill Lab runs your skill 20–50 times against the same task in identical
containers, then tells you what actually varied.

## Why you should care

Here is a real finding from `examples/architecture-docs/` in this repo. The
setup, which you can reproduce:

- **The skill** (`skills/v1`) — four lines telling the agent to identify the
  components of an application and write a Markdown document describing them.
  The kind of skill you'd write in five minutes and consider done.
- **The repository** — a small Python service whose architecture notes are
  scattered and partly wrong: `docs/architecture.md` is stale, the README has
  its own outdated "Architecture" paragraph, and `CONTRIBUTING.md` says where
  docs are supposed to live.
- **The prompt** — "Create architecture documentation for this application."

Run it 20 times and every run produces a decent document. Nothing looks wrong.
But the runs disagreed about something the skill never mentioned:

```
Observed behavior                            v1      v2
Updated the contradicting README section   10/20   20/20
Read CONTRIBUTING.md for doc conventions    0/20   17/20
Document well over the length guidance     12/20    0/20
Modified source code (it shouldn't)          0/20    0/20
```

Half the runs fixed the README so it matched the new document; half left the
repository contradicting itself. A coin flip — invisible if you run the skill
once, and easy to blame on "the model" if a user ever reports it.

Skill Lab reported the split, traced it to the skill's silence about existing
documentation, and proposed the instruction to add. `v2` is that skill with the
proposed sentences added; the right-hand column is 20 fresh runs of it. The
same comparison also caught something new the edit introduced: 3 of 20 v2 runs
ignored the new "check CONTRIBUTING.md" instruction — the next thing to fix.

These are observed behavioral frequencies, not quality scores. Skill Lab never
claims a document was good; it reports what the agent did and how consistently.

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

```
  your skill + repo fixture + prompt
                 │
                 ▼
        ┌──────────────────┐
        │   Skill Lab      │  builds a Harbor task: a Dockerfile that copies the
        │   (experiment)   │  fixture to /app and commits it as the baseline
        └────────┬─────────┘
                 │  harbor run --n-attempts 20
                 ▼
        ┌──────────────────┐
        │     Harbor       │  20 isolated containers, each installing and running
        │  (execution)     │  Claude Code from the identical baseline
        └────────┬─────────┘
                 │  per trial: ATIF trajectory + the whole /app workspace
                 ▼
        ┌──────────────────┐
        │   Normalizer     │  → runs/NNN/run.json: tool calls, commands, files
        │                  │    created/modified/deleted, git diff, tokens, cost
        └────────┬─────────┘
                 ▼
        ┌──────────────────┐
        │   Summarizer     │  one LLM call per run: what it did, notable
        │   (per run)      │    behaviors, possible problems — never a grade
        └────────┬─────────┘
                 ▼
        ┌──────────────────┐
        │  Cross-run       │  clusters, recurring problems, outliers, strong runs,
        │  analyzer        │    suggested SKILL.md edits — each citing run ids
        └────────┬─────────┘
                 ▼
          analysis.json + report.md        (and `compare` for v1 vs v2)
```

### Harbor does the execution

[Harbor](https://github.com/laude-institute/harbor) (Laude Institute) is an
open framework for running coding agents in containers. Skill Lab does not
reimplement any of it, and treats it as an external runtime driven through its
CLI:

| Harbor provides | Used here for |
|---|---|
| Containerized trials from one image | Every run starts from a byte-identical repository |
| Agent installation (~40 agents) | Claude Code installed inside the container |
| `--n-attempts`, `--n-concurrent` | The 20–50 repetitions, in parallel |
| Skill injection (`--skill`) | Putting the `SKILL.md` under test in front of the agent |
| ATIF trajectories | The behavioral record: every tool call, argument, and result |
| Artifact collection | Pulling the finished workspace back out, `.git` included |
| Simulated user (`--bridge acp`) | Skills that ask questions (see below) |

Harbor's own purpose is benchmarking — run a task, score it with tests. Skill
Lab uses the execution half and **disables the verifier entirely**: there is no
reward, because the point is to observe behavior, not score it.

### Skill Lab does the analysis

Everything after execution: normalizing each trial into a `RunRecord`,
computing the workspace diff, summarizing runs, finding cross-run patterns,
and comparing skill versions. Harbor's on-disk layout is known to exactly two
modules (`harbor/runner.py`, `harbor/parser.py`) so the rest of the codebase —
and a future second agent backend — is insulated from it.

`docs/harbor-spike.md` documents every Harbor behavior this depends on, each
verified by running it rather than taken from documentation, including the
workarounds needed for interactive mode. `skill-lab-project.md` is the original
design document.

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

## What an experiment leaves behind

Every claim in a report names the runs it rests on, and every run keeps the raw
evidence behind it — so "8 of 20 runs did X" is something you can go read.

Experiments live under `.skill-lab/experiments/<name>/`:

```
experiment.yaml     # exactly what was run: skill digest, fixture digest + commit,
                    #   prompt, agent, model, Harbor version, timestamps
skill/              # snapshot of the skill as it ran, so later analysis reads the
                    #   version that produced these runs, not your latest edit
task/               # the generated Harbor task (Dockerfile, instruction, config)
harbor/<name>/      # Harbor's output: one trial directory per attempt
runs/NNN/           # run.json      — the normalized RunRecord
                    #   diff.patch    — what this run changed, in full
                    #   summary.json  — the per-run behavioral summary
analysis.json       # machine-readable findings, each with run ids
report.md           # the same findings, written for a skill author to read
```

Reproducibility is the reason for the digests: an experiment records the exact
skill contents and fixture contents it used, so `compare` can warn you when two
experiments differ in more than the skill — a different prompt, a changed
fixture, another model — instead of silently attributing that to your edit.

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
