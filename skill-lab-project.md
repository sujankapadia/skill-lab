# Skill Lab MVP

## Purpose

Build a small tool that helps authors improve an agent skill by running the same skill multiple times in a controlled environment, collecting what the agent actually did, and analyzing variation across runs.

The MVP is **not** an eval framework.

It should not require the skill author to define expected outputs, pass/fail criteria, custom verifiers, reward functions, or a large test harness.

The initial goal is simpler:

> Run a skill 20–50 times against the same realistic task, collect behavior and workspace changes from every run, identify recurring patterns and outliers, compare stronger and weaker executions, and produce actionable feedback about how the skill could be improved.

Use **Harbor** as the rollout/execution substrate rather than building our own sandbox or agent runner.

---

# 1. Core Product Idea

Today, improving a skill often looks like this:

```text
author writes skill
      ↓
humans use it
      ↓
someone eventually encounters a problem
      ↓
problem gets reported
      ↓
author reproduces it
      ↓
skill gets changed
      ↓
wait for more feedback
```

We want to tighten that loop:

```text
author writes skill
      ↓
run skill 20–50 times automatically
      ↓
collect trajectories + workspace changes + artifacts
      ↓
summarize each run
      ↓
compare runs
      ↓
identify:
  - recurring errors
  - deviations
  - inconsistent behavior
  - unusual runs
  - better-than-average runs
  - patterns associated with better outcomes
      ↓
suggest likely SKILL.md improvements
      ↓
author edits skill
      ↓
rerun same experiment
      ↓
compare behavior before vs. after
```

The tool should help answer questions like:

- What does the agent usually do when this skill is active?
- How consistent is its behavior?
- What different strategies emerge across repeated runs?
- What goes wrong repeatedly?
- Are some runs noticeably cleaner or more effective than others?
- What do the strongest runs have in common?
- What do the problematic runs have in common?
- Does the skill appear ambiguous in any important area?
- What instructions in `SKILL.md` might reduce bad behavior or encourage better behavior?
- After editing the skill, did behavior improve?

---

# 2. Important MVP Constraints

Keep the first version intentionally narrow.

## In scope

- One local skill directory containing `SKILL.md`
- One manually supplied task/prompt
- One manually supplied repository fixture
- Linux/Docker environment
- Claude Code first
- Codex support second if easy
- 20–50 repeated executions
- Each execution starts from the same baseline repository state
- Capture Harbor trajectory data
- Capture final workspace state or enough information to reconstruct a diff
- Normalize every run into a common `RunRecord`
- Summarize each run with an LLM
- Analyze all runs together
- Identify behavior clusters, outliers, recurring problems, and strong runs
- Produce actionable feedback for improving the skill
- Allow rerunning the same experiment against a new skill version
- Compare two experiment results

## Explicitly out of scope for V1

Do **not** build these yet:

- a general-purpose eval framework
- pass/fail scoring
- custom verifier DSL
- reward functions
- GEPA integration
- automatic skill rewriting
- automatic scenario generation
- browser/computer-use environments
- real external services
- MCP orchestration
- arbitrary network access
- multi-container applications
- databases
- image generation or image-specific grading
- embeddings/vector database
- a hosted web UI
- a custom sandbox
- a custom agent runtime
- a Harbor fork

Harbor already provides the foundation for many of these later.

---

# 3. High-Level Architecture

```text
                     USER
                      │
                      │ skill + prompt + repo
                      ▼
              ┌────────────────┐
              │   Skill Lab    │
              │      CLI       │
              └───────┬────────┘
                      │
                      │ create Harbor job
                      ▼
              ┌────────────────┐
              │     Harbor     │
              │                │
              │ 20–50 isolated │
              │    trials      │
              └───────┬────────┘
                      │
           Harbor job/trial directories
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
     ATIF trajectory        final workspace /
     + metadata             collected artifacts
          │                       │
          └───────────┬───────────┘
                      ▼
              ┌────────────────┐
              │ Run Normalizer │
              └───────┬────────┘
                      │
                  RunRecord[]
                      │
                      ▼
              ┌────────────────┐
              │ Run Summarizer │
              │  one per run   │
              └───────┬────────┘
                      │
                 RunSummary[]
                      │
                      ▼
              ┌────────────────┐
              │ Cross-Run      │
              │ Analyzer       │
              └───────┬────────┘
                      │
                      ▼
              analysis/report.md
```

Harbor should own execution.

Skill Lab should own:

1. experiment configuration
2. Harbor invocation
3. Harbor result parsing
4. workspace comparison
5. per-run behavior summarization
6. cross-run analysis
7. experiment comparison

---

# 4. Why Harbor

Do not reinvent the execution layer.

Use upstream Harbor for:

- isolated runs
- repeatable environments
- agent execution
- skill injection
- multiple attempts
- concurrency
- trajectory capture
- token/cost metadata
- artifact collection
- job/trial organization
- future extensibility to other environments and agents

The Skill Lab code should treat Harbor as an external runtime.

Avoid depending on internal Harbor implementation details unless necessary.

Prefer:

- Harbor CLI
- Harbor documented configuration
- Harbor output/job files
- Harbor ATIF trajectories

Do not fork Harbor for the MVP.

---

# 5. First Experiment

The first end-to-end experiment should be intentionally simple.

Example:

```text
Skill:
./skills/architecture-documentation/

Repository:
./fixtures/sample-app/

Prompt:
Create architecture documentation for this application.

Agent:
Claude Code

Attempts:
20
```

Expected workflow:

```bash
skill-lab run \
  --skill ./skills/architecture-documentation \
  --repo ./fixtures/sample-app \
  --prompt "Create architecture documentation for this application." \
  --attempts 20 \
  --agent claude-code
```

Conceptually Skill Lab should configure Harbor to:

```text
skill = local skill directory
environment = clean copy of sample-app
attempts = 20
verifier = disabled
artifact/workspace collection = enabled
```

Each run must start from the exact same repo state.

---

# 6. Proposed CLI

Start with three commands.

## `skill-lab run`

Runs an experiment.

Example:

```bash
skill-lab run \
  --skill ./skills/architecture \
  --repo ./fixtures/sample-app \
  --prompt-file ./prompts/architecture.md \
  --attempts 20 \
  --agent claude-code
```

Useful options:

```text
--skill
--repo
--prompt
--prompt-file
--attempts
--agent
--concurrency
--name
--output
```

Output:

```text
Experiment: architecture-baseline
Skill digest: <digest>
Agent: claude-code
Attempts: 20

20/20 trials completed
Harbor job: .skill-lab/jobs/architecture-baseline/...
```

Then automatically normalize and analyze unless `--no-analyze` is passed.

---

## `skill-lab analyze`

Analyze an existing Harbor/Skill Lab experiment.

```bash
skill-lab analyze .skill-lab/experiments/architecture-baseline
```

Output should include:

```text
20 executions analyzed

Behavior clusters:
A. Inspect existing docs → inspect source → update/create docs     12
B. Inspect source → immediately create architecture.md             6
C. Documentation task + unrelated source modifications              2

Recurring concerns:
- 8 runs created a new architecture document without first searching
  for existing architecture documentation.
- 2 runs modified application source during a documentation-only task.

Strong runs:
#3, #8, #17

Strong-run characteristics:
- searched for existing documentation first
- inspected package/module boundaries
- made minimal workspace changes
- did not modify source

Potential SKILL.md improvements:
1. Require discovery of existing architecture documentation before
   creating a new artifact.
2. Explicitly prohibit source changes for documentation-only requests.
3. Require inspection of package/module boundaries before writing.
```

---

## `skill-lab compare`

Compare two experiments.

```bash
skill-lab compare \
  .skill-lab/experiments/architecture-v1 \
  .skill-lab/experiments/architecture-v2
```

Example output:

```text
Behavior change                         v1        v2

Searched existing docs                 60%       95%
Created duplicate/new doc              30%        5%
Modified source unnecessarily          10%        0%
Inspected module boundaries            75%       95%

Behavior consistency:
v1: medium
v2: high

Major improvement:
The v2 skill much more consistently checks for existing documentation
before writing.

Remaining issue:
2/20 runs still produced architecture documentation before examining
important application modules.
```

Do not pretend these percentages are formal quality scores.

They are observed behavioral frequencies.

---

# 7. Experiment Manifest

Each experiment should store a stable manifest.

Example:

```yaml
id: architecture-v1
created_at: 2026-09-14T15:00:00Z

skill:
  path: ./skills/architecture
  digest: sha256:...

repository:
  source: ./fixtures/sample-app
  git_commit: abc123...

agent:
  name: claude-code
  model: null

prompt:
  text: "Create architecture documentation for this application."

execution:
  attempts: 20
  concurrency: 4

harbor:
  job_path: ./harbor-job
```

Persist this file in the experiment directory.

The skill digest is important so that results can be traced to the precise skill contents used.

---

# 8. Experiment Directory Layout

Suggested layout:

```text
.skill-lab/
└── experiments/
    └── architecture-v1/
        ├── experiment.yaml
        ├── harbor/
        │   └── <Harbor job output>
        │
        ├── runs/
        │   ├── 001/
        │   │   ├── run.json
        │   │   ├── summary.json
        │   │   ├── diff.patch
        │   │   └── diff-stat.json
        │   ├── 002/
        │   └── ...
        │
        ├── analysis.json
        └── report.md
```

Avoid copying data unnecessarily.

If Harbor already owns large artifact/workspace directories, `run.json` may simply reference those paths.

---

# 9. RunRecord

Normalize every Harbor trial into a common structure.

Initial shape:

```python
class RunRecord:
    experiment_id: str
    run_id: str

    completed: bool
    error: str | None

    final_response: str | None

    duration_seconds: float | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None

    tool_calls: list[ToolCall]
    commands: list[str]

    files_created: list[str]
    files_modified: list[str]
    files_deleted: list[str]

    diff_patch_path: str | None
    diff_stats: DiffStats | None

    harbor_trial_path: str
    trajectory_path: str | None
    workspace_path: str | None
```

Do not over-engineer this schema.

Add fields only as real experiments demonstrate a need.

---

# 10. Workspace Change Collection

For V1, repository skills are the primary target.

Every trial starts from an identical Git repository fixture.

After the agent finishes, collect enough state to answer:

- what files were created?
- what files changed?
- what files were deleted?
- what is the Git diff?
- how large was the change?

Preferred mechanism:

```bash
git status --porcelain
git diff --binary
git diff --stat
```

If untracked files are created, include them in the run record.

Possible output:

```json
{
  "files_created": [
    "docs/architecture.md"
  ],
  "files_modified": [
    "README.md"
  ],
  "files_deleted": [],
  "diff_stats": {
    "files_changed": 2,
    "insertions": 141,
    "deletions": 4
  }
}
```

Do not attempt deep semantic code analysis in V1.

---

# 11. Trajectory Parsing

Use Harbor's ATIF trajectory as the primary behavioral source.

Extract useful information such as:

- assistant messages
- tool names
- shell commands
- file reads
- file writes
- tool-call sequence
- errors
- environment/tool responses
- token/cost metadata

Do not build a complex trace model initially.

The main goal is to give the summarizer enough evidence to describe what the run did.

Consider studying and borrowing implementation ideas from SkillAudit's Harbor run-record parser, but keep this project's data model simpler.

---

# 12. Per-Run Summarization

Each run should be converted into a compact structured behavioral summary.

The summarizer should receive:

- original prompt
- `SKILL.md`
- final answer
- relevant trajectory evidence
- commands/tool calls
- workspace diff summary
- optionally selected diff content

Ask the model to describe **what happened**, not to produce a binary grade.

Suggested output schema:

```json
{
  "approach": "Short description of the strategy used",
  "steps": [
    "searched existing documentation",
    "inspected source modules",
    "created docs/architecture.md"
  ],
  "outcome": "Description of resulting work",
  "notable_behaviors": [
    "looked for existing documentation before writing"
  ],
  "possible_problems": [
    "did not inspect the worker package"
  ],
  "strengths": [
    "minimal workspace changes"
  ],
  "uncertainties": [
    "cannot determine whether architecture description is fully accurate"
  ]
}
```

Important:

The model should distinguish:

- observed fact
- inference
- uncertainty

Do not force a pass/fail field.

---

# 13. Cross-Run Analysis

This is the most important component in the MVP.

Input:

```text
SKILL.md
prompt
20–50 RunRecords
20–50 RunSummaries
```

Goal:

Find useful patterns across runs.

The analyzer should identify:

## Recurring behavior

Example:

```text
17/20 runs inspect package.json first.
```

## Behavioral variants

Example:

```text
Three common approaches emerged:

A. Search docs → inspect code → update docs
B. Inspect code → create new docs
C. Immediately create docs
```

## Recurring problems

Example:

```text
6 runs create new architecture documentation despite an existing
architecture document.
```

## Outliers

Example:

```text
Run #19 changed 14 source files; every other run changed 0–2 files.
```

## Strong runs

A "strong run" is not necessarily defined by an objective verifier.

The analyzer can identify runs that appear especially:

- focused
- efficient
- complete
- conservative
- well-reasoned
- aligned with the task
- consistent with the skill's stated intent

The analyzer must explain why it considers them strong.

Example:

```text
Runs #3, #8, and #17 appear strongest because they:

- searched for existing docs first
- inspected relevant package boundaries
- produced focused documentation
- did not make unrelated changes
```

## Likely skill deficiencies

Example:

```text
The skill repeatedly produces two competing behaviors because
SKILL.md says "create architecture documentation" but does not state
whether existing architecture documentation should be updated first.
```

## Suggested skill improvements

Example:

```text
Consider adding:

"Before creating new architecture documentation, search the repository
for existing architecture documents and update them when appropriate."
```

Suggestions should be tied to observed evidence.

---

# 14. Analysis Report

Generate both:

```text
analysis.json
report.md
```

`analysis.json` should be machine-readable.

Possible shape:

```json
{
  "run_count": 20,

  "clusters": [
    {
      "name": "inspect-first",
      "run_ids": ["1", "3", "8"],
      "description": "..."
    }
  ],

  "recurring_patterns": [],
  "recurring_problems": [],
  "outliers": [],
  "strong_runs": [],

  "skill_observations": [],
  "suggested_changes": []
}
```

`report.md` should be optimized for a skill author to read.

---

# 15. Prompt Design for the Analyzer

The analyzer must not behave as if it has ground truth when it does not.

Good framing:

> You are analyzing repeated executions of the same agent skill.
>
> Your job is not to declare the skill correct or incorrect.
>
> Identify recurring behavior, deviations, apparent errors, meaningful
> variation, unusually strong runs, and likely causes in the skill
> instructions.
>
> Clearly separate directly observed evidence from inference.
>
> When suggesting a change to SKILL.md, cite the recurring behavior
> that motivates the change.

Avoid prompts like:

```text
"Grade each run."
```

Prefer:

```text
"What differs across these executions, and what would a skill author
want to know?"
```

---

# 16. Handling Context Size

For 20 runs, a single analyzer call may be sufficient if summaries are compact.

For larger experiments, use hierarchical summarization.

Example:

```text
runs 1–10   → batch summary A
runs 11–20  → batch summary B
runs 21–30  → batch summary C
runs 31–40  → batch summary D
runs 41–50  → batch summary E

A–E → final cross-run analysis
```

Do not introduce embeddings or vector clustering until scale requires them.

The MVP should prefer simple LLM-assisted clustering.

---

# 17. Version Comparison

Once one experiment works, version comparison is the highest-value second feature.

Workflow:

```text
SKILL.md v1
   ↓
20 runs
   ↓
analysis

edit skill

SKILL.md v2
   ↓
same repo
same prompt
same agent
20 runs
   ↓
analysis

compare
```

The comparator should identify changes in observed behavior.

Example:

```text
Observation                               v1       v2

Searched for existing docs              12/20    19/20
Created new doc immediately              6/20     1/20
Modified source during docs task         2/20     0/20
Inspected package boundaries            15/20    19/20
```

Again:

These are **behavior frequencies**, not quality metrics.

Also ask the model:

```text
What changed materially?
Which apparent problems improved?
Did any new behavior appear?
What remains inconsistent?
```

---

# 18. Model Abstraction

Do not tightly couple analysis to one provider.

Use a very small interface:

```python
class AnalysisModel(Protocol):
    def generate_json(
        self,
        system_prompt: str,
        prompt: str,
        schema: dict
    ) -> dict:
        ...
```

For the first implementation, support whichever API is easiest.

Keep provider abstractions minimal.

---

# 19. Harbor Integration Strategy

Before coding deeply, inspect the latest upstream Harbor source/docs and confirm:

1. how to run a local skill
2. how to specify multiple attempts
3. how to disable or omit verification
4. how to capture artifacts/workspace state
5. exact Harbor job/trial directory layout
6. exact ATIF trajectory path/schema
7. whether skill digests are directly available in output
8. best supported way to invoke Harbor programmatically

Prefer invoking Harbor using its documented Python API if stable.

Otherwise shell out to the Harbor CLI.

Do not duplicate Harbor behavior.

Implement a narrow adapter:

```python
class HarborRunner:
    def run(experiment: ExperimentConfig) -> HarborJob:
        ...
```

And a parser:

```python
class HarborJobParser:
    def trials(job: HarborJob) -> list[HarborTrial]:
        ...
```

The rest of Skill Lab should not know Harbor filesystem details.

---

# 20. Suggested Python Package Structure

```text
skill-lab/
├── pyproject.toml
├── README.md
│
├── src/
│   └── skill_lab/
│       ├── cli.py
│       │
│       ├── models/
│       │   ├── experiment.py
│       │   ├── run_record.py
│       │   ├── run_summary.py
│       │   └── analysis.py
│       │
│       ├── harbor/
│       │   ├── runner.py
│       │   ├── parser.py
│       │   └── trajectory.py
│       │
│       ├── workspace/
│       │   └── git_diff.py
│       │
│       ├── analysis/
│       │   ├── model.py
│       │   ├── summarize_run.py
│       │   ├── analyze_runs.py
│       │   └── compare.py
│       │
│       └── reporting/
│           └── markdown.py
│
├── prompts/
│   ├── summarize-run.md
│   ├── analyze-runs.md
│   └── compare-experiments.md
│
├── tests/
│   ├── test_harbor_parser.py
│   ├── test_git_diff.py
│   └── test_analysis_serialization.py
│
└── examples/
    └── architecture-docs/
        ├── skill/
        │   └── SKILL.md
        ├── repo/
        └── prompt.md
```

Keep the package small.

---

# 21. Implementation Phases

## Phase 0 — Harbor spike

Before building the product:

- install Harbor
- create a trivial local skill
- create a tiny Git repo fixture
- run Claude Code through Harbor
- use `n_attempts = 3`
- disable verifier
- inspect Harbor output
- locate trajectory
- verify every run starts clean
- capture final workspace

Deliverable:

```text
Three Harbor runs with:
- trajectory
- final response
- final repo state
```

Stop here if Harbor cannot reliably provide this.

---

## Phase 1 — Normalize runs

Build:

```text
Harbor output
    ↓
RunRecord
```

Extract:

- final response
- timing
- token/cost info
- commands/tool calls
- workspace changes
- trajectory reference

Deliverable:

```bash
skill-lab inspect <experiment>
```

which prints a compact table of all runs.

Example:

```text
RUN   TIME   TOOLS   FILES   +LINES  -LINES

1      83s      31       1      124       0
2      91s      27       2      181      12
3      72s      19       1       98       0
```

No LLM analysis yet.

---

## Phase 2 — Summarize one run

Build per-run LLM summarization.

Input:

```text
RunRecord + selected trajectory evidence
```

Output:

```text
RunSummary
```

Manually inspect whether summaries accurately describe the runs.

---

## Phase 3 — Analyze 20 runs

Implement cross-run analysis.

Deliverable:

```bash
skill-lab analyze <experiment>
```

producing:

```text
analysis.json
report.md
```

This is the first real product milestone.

---

## Phase 4 — Compare skill versions

Implement:

```bash
skill-lab compare experiment-v1 experiment-v2
```

This demonstrates the feedback loop.

---

# 22. Definition of Done for the MVP

The MVP is successful if we can demonstrate this:

1. Take one real `SKILL.md`.
2. Take one realistic repository.
3. Take one realistic prompt.
4. Execute it 20 times with Claude Code using Harbor.
5. Each run begins from the same repo state.
6. Collect the trajectory and final workspace behavior.
7. Automatically summarize each execution.
8. Automatically identify multiple behavioral patterns.
9. Surface at least one meaningful recurring problem or deviation.
10. Identify at least one particularly strong or interesting run and explain why.
11. Generate at least one plausible SKILL.md improvement tied to observed behavior.
12. Edit the skill.
13. Run another 20 executions.
14. Compare before vs. after behavior.

If we can do this convincingly, the concept is validated.

---

# 23. What Success Should Feel Like

The user experience should feel like:

```text
$ skill-lab run \
    --skill ./my-skill \
    --repo ./sample-project \
    --prompt "Create architecture documentation." \
    --attempts 20

Running 20 trials...
████████████████████ 20/20

Analyzing behavior...

Three recurring execution strategies emerged.

A — Discover existing docs, inspect code, then update/create docs
    12 runs

B — Inspect code, immediately create architecture.md
     6 runs

C — Modify source while producing documentation
     2 runs

Recurring concern:
8 runs created a new architecture document without checking whether
one already existed.

Strong runs:
#3, #8, #17

Those runs consistently:
- searched existing documentation first
- inspected package boundaries
- made small focused changes

Likely skill ambiguity:
SKILL.md tells the agent to create architecture documentation but does
not explicitly tell it to discover/update existing documentation.

Suggested change:
"Before creating new architecture documentation, search for existing
architecture documentation and update it when appropriate."

Report:
.skill-lab/experiments/architecture-v1/report.md
```

That is enough for V1.

---

# 24. Principles

## Observe before scoring

The first version is about collecting and understanding behavior.

Do not prematurely force everything into:

```text
pass
fail
score
```

## Reproducibility matters

Record:

- skill digest
- repo commit
- prompt
- agent
- model if known
- Harbor version
- timestamps
- experiment settings

## Keep evidence

Every conclusion should be traceable back to actual runs.

## Human remains the skill editor

The system may suggest changes.

It should not automatically rewrite `SKILL.md` in V1.

## Strong runs matter as much as failures

The system should search for:

```text
what went wrong?
```

and:

```text
what unexpectedly went right?
```

A better run may reveal instructions worth making explicit.

## Do not reinvent infrastructure

Harbor is the runner.

Skill Lab is the behavior-analysis layer.

---

# 25. Later Extensions — Do Not Build Yet

Once the basic loop works, possible extensions include:

## Multiple prompts

```text
skill
  ×
10 prompts
  ×
5 attempts each
```

## Prompt variation

Generate semantically related prompts to probe robustness.

## User-derived scenarios

Turn real reported problems into reusable experiments.

## Deterministic observations

Automatically detect:

- tests pass
- build passes
- protected files changed
- duplicate files
- invalid output

These may eventually become lightweight eval signals.

## Browser environments

Use Harbor's browser/computer-use environment support.

## Network/service environments

Use controlled network access and Docker Compose.

## Skill comparison

Compare:

```text
skill A
vs.
skill B
```

on the same scenarios.

## Automatic optimization

Potential future GEPA integration:

```text
SKILL.md
    ↓
rollouts
    ↓
analysis
    ↓
candidate skill revision
    ↓
rollouts
    ↓
holdout comparison
```

Do not implement this until the human-guided feedback loop is useful.

---

# 26. Open Questions to Resolve During the Harbor Spike

Do not speculate. Inspect Harbor and answer these experimentally.

1. What is the cleanest Harbor configuration for a local `SKILL.md`?
2. Does every attempt automatically receive a clean environment?
3. How should we preserve the complete final repo?
4. Can Harbor capture a patch/diff directly, or should Skill Lab do it afterward?
5. What exact information is present in ATIF trajectories for Claude Code?
6. Does Harbor expose the skill digest in the trial/job metadata?
7. Is the Python API stable enough, or should V1 shell out to the CLI?
8. What happens when an agent trial crashes or times out?
9. What token/cost fields are available?
10. How much workspace/artifact data does Harbor retain by default?
11. Can a trial reference its baseline environment/repo state cleanly?
12. What Harbor version should this project pin initially?

Document the answers in:

```text
docs/harbor-spike.md
```

before adding abstractions around uncertain behavior.

---

# 27. First Coding Task

Start here:

> Build the smallest possible Harbor spike that takes:
>
> - a local skill directory
> - a local Git repository
> - a prompt
> - an attempt count
>
> and runs Claude Code multiple times against clean copies of that repository.
>
> After execution, print for every trial:
>
> - completion status
> - final response
> - trajectory path
> - workspace path
> - files created
> - files modified
> - files deleted
> - Git diff statistics
> - duration
> - token/cost information when available
>
> Do not implement LLM analysis yet.
>
> Do not implement a general framework.
>
> Use upstream Harbor.
>
> The purpose of this spike is to prove that Harbor can reliably generate the behavioral dataset we need.

Once that works, commit it before moving on to summarization.

---

# 28. Product Thesis

The project is not trying to answer:

> "Can we formally prove that this skill is correct?"

It is trying to answer:

> "If I let this skill run many times, what can I learn about how it behaves, where it goes wrong, where it varies, and what the best executions teach me about how the skill should be written?"

If we can make that loop cheap and fast, skill authors can improve skills with far less dependence on slow human trial-and-error feedback.
