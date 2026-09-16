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

### How the workspace diff is produced

"What did this run change?" is the other half of the evidence, alongside the
trajectory. It is a plain `git diff`, taken in three stages:

**1. The baseline is baked into the image**, not created per trial:

```dockerfile
WORKDIR /app
COPY repo/ /app/
RUN git init -q && git add -A && git commit -qm "baseline"
```

Because the commit lives in the image, all 20 containers start from a
byte-identical tree at the same commit — which is what makes the runs
comparable at all.

**2. Harbor extracts the finished workspace.** The generated `task.toml`
declares `[[artifacts]] source = "/app"`, so after the agent stops, Harbor tars
that directory out to `<trial>/artifacts/app/` — `.git` included, so the
baseline commit travels with it.

**3. Skill Lab diffs it on the host**, after the container is gone
(`workspace/git_diff.py`):

```bash
git -C <workspace> status --porcelain --untracked-files=all   # created/modified/deleted
GIT_INDEX_FILE=<abs>/.git/skill-lab-index git add -A          # stage into a scratch index
git diff --cached --numstat HEAD                              # stats
git diff --cached --binary HEAD                               # the patch
```

Untracked files never show up in `git diff`, so everything is staged first —
but into a throwaway index file, leaving the downloaded workspace's own index
untouched. The results become `runs/NNN/diff.patch` and `diff-stat.json`, plus
the file lists and line counts on the `RunRecord`.

Doing this on the host rather than in the container is deliberate: Harbor has
no diff feature, its one pre-collection hook belongs to the verifier phase we
disable, and host-side diffing still works when a trial times out or crashes,
since Harbor downloads `/app` either way.

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
  --attempts 10 --concurrency 4 --name arch-v1

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
  --attempts 10 --name arch-v2
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
runs/NNN/           # run.json        — the normalized RunRecord
                    #   trajectory.json — the run's own copy of the ATIF trajectory
                    #   diff.patch      — what this run changed, in full
                    #   summary.json    — the per-run behavioral summary
analysis.json       # machine-readable findings, each with run ids
report.md           # the same findings, written for a skill author to read
```

`runs/` is self-contained: each run keeps its own trajectory (~100 KB), so you
can delete the bulky `harbor/` job directory — container logs, session files,
workspace copies — and still re-summarize, re-analyze and compare. Workspaces
stay referenced in place rather than copied; they are the large ones.

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
  --attempts 10 --name sow-v1
```

`inspect` gains REPLIES (messages the simulated user sent) and WAITING (the run
ended on an unanswered question); the evidence the summarizer sees is the full
transcript. `--apt` adds packages the skill needs in the image.

### What this does and does not test

It is a **text channel**. The simulated user answers prose questions with
prose. `AskUserQuestion` — Claude Code's structured multiple-choice prompt — is
not available to the agent in either headless or ACP mode: across 20 runs of a
skill built around it, every run searched for the tool, got "No matching
deferred tools found", and fell back to asking in plain text. None ever called
it.

So for a skill whose instructions say "gather parameters using
`AskUserQuestion` in rounds", these runs exercise its **fallback path**, not
its intended one. You can still learn a lot from that — whether the agent asks
for everything it needs, builds a valid config, handles the answers correctly,
and what it does when the prescribed mechanism is missing (in our case: 18 of
20 runs silently collapsed four staged rounds into one wall of text, which the
skill gives no guidance for). You cannot learn whether the multiple-choice flow
itself works well.

This is not something Skill Lab can fix locally. A structured question would
have to be surfaced by the ACP adapter, routed by `acpx`, and answered by the
simulated user — and the middle link has no path for it: `acpx` resolves
agent-initiated requests from a static policy, or denies them when there is no
TTY, and the simulated user is a client issuing one message at a time with no
way to receive a mid-turn callback.

Interactive runs also have a second cost you may not expect: the simulated user
is itself an agent, so it consumes tokens too. Harbor tracks its usage
separately from the target's, and `skill-lab usage` does not yet include it.

## Tests

```bash
uv run pytest
```

## How many runs?

The default is **10**. We ran both worked examples at 20 and then checked what
the first 10 would have shown:

| finding | first 10 | all 20 |
|---|---|---|
| the 10/20 README split (the headline finding) | 4/10 | 10/20 |
| the regression the v2 edit introduced | 2/10 | 2/20 |
| a generator crash in the SOW skill | 3/10 | 6/20 |
| document length spread | 66–115 | 66–116 |

Every finding was already visible at 10; the second ten bought precision on the
ratio, not new information — and halving the runs halves the token cost, since
both the trials and the per-run summaries scale with it.

Raise it to 20 when the *number* matters rather than the finding: a v1 vs v2
comparison you will act on, or when you suspect something rarer than the runs
have shown. For a behavior that truly occurs 10% of the time, 10 runs show you
nothing about a third of the time; 20 runs, about an eighth.

Resist reaching for a cheaper analysis model to save instead. Summarizing with
Haiku is ~28% cheaper but measurably worse at the thing this tool exists for —
in a side-by-side on 20 runs it missed one of the two runs that ignored an
explicit skill instruction, and the cross-run analyzer then called that run
*strong*. Fewer runs costs you precision; a weaker summarizer costs you
findings. If you want a cheap first look, `analyze --model haiku` and then
re-run `summarize --force` with the default before acting on it — the stored
trajectories make that re-runnable without re-running the trials.

## Cost and usage

Rollouts are not the whole bill. An experiment also makes one summary call per
run plus one cross-run call, and on a subscription those draw from the same
allowance. Measured on a 20-run experiment (halve it for the default 10):

```bash
uv run skill-lab usage arch-v1
```
```
Rollouts   ( 20 runs):  4,514,189 in (4,316,069 cached) / 76,659 out  $2.42
Summaries  ( 20 calls): 565,000 in (347,000 cached) / 73,000 out      $1.80
Analysis   (  1 call):  7,924 in / 3,317 out                          $0.07
```

Costs are estimates (LiteLLM pricing for rollouts, the CLI's own figure for
analysis calls) — on a subscription nothing is billed per token. Usage is
recorded on each `summary.json` and on `analysis.json`; `analyze` prints the
breakdown when it finishes. On short experiments the analysis side can cost
more than the runs themselves, so `--model haiku` for summarization is the
first lever if you are near a limit.

## Billing

Rollouts and analysis calls run on your Claude subscription by default:

```bash
claude setup-token                                # one-time, prints a token
export CLAUDE_CODE_OAUTH_TOKEN=...                # put it in ~/.zshrc
```

Pass `--auth api` to bill `ANTHROPIC_API_KEY` instead.
