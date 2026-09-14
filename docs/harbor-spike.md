# Harbor spike (Phase 0)

Date: 2026-09-14. Harbor **0.23.0** (`uv tool install harbor`), Claude Code 2.1.270
inside the container, model `claude-sonnet-5`, Docker Desktop 29.4.0 on macOS.

Everything below was verified by running it, not read from docs. Source references
are to the installed package at `harbor/` in the uv tool site-packages.

## What was run

```bash
python3 src/skill_lab/spike.py \
  --skill ./examples/architecture-docs/architecture-documentation \
  --repo  ./examples/architecture-docs/repo \
  --prompt-file ./examples/architecture-docs/prompt.md \
  --attempts 3 --concurrency 3 --name spike-3
```

Result: 3/3 trials completed in 2m33s wall-clock (~30s agent time each, ~$0.08–0.09
each). Every trial produced an ATIF trajectory, a final response, a downloaded final
workspace, and a git diff against the shared baseline. A separate probe with
`--agent-timeout 15` confirmed timeout handling (see Q8).

The spike generates a Harbor task directory on the fly and shells out to `harbor run`:

```
<output>/<name>/task/
├── instruction.md        # the prompt
├── task.toml             # agent timeout + [[artifacts]] source="/app"
├── tests/test.sh         # placeholder; verification is disabled
└── environment/
    ├── Dockerfile        # ubuntu:24.04 + git/python, COPY repo/ /app/, git init + baseline commit
    └── repo/             # copy of the fixture (minus .git, caches)
```

```
harbor run --path <task> --agent claude-code --model anthropic/claude-sonnet-5 \
  --skill <skill-dir> --n-attempts N --n-concurrent C --disable-verification \
  --jobs-dir <output>/<name>/harbor --job-name <name>
```

## Answers to the §26 open questions

### 1. Cleanest Harbor configuration for a local `SKILL.md`

`harbor run --skill <local-dir>`. The directory must contain `SKILL.md` directly (or
be a root whose immediate children each contain one). Harbor copies it into the
container at `/harbor/skills/<dirname>` and Claude Code's agent adapter then runs
`cp -r /harbor/skills/* $CLAUDE_CONFIG_DIR/skills/` before launch
(`agents/installed/claude_code.py::_build_register_skills_command`).

**Gotcha:** the skill's name, as seen by the agent, is the **directory name**, not the
`name:` in the SKILL.md frontmatter. With the dir named `skill/`, the trajectory showed
`Skill {"skill": "skill"}`. The example dir was renamed to `architecture-documentation/`
to match. Skill Lab should validate dir name == frontmatter name (or warn).

Observed in every trial: the very first agent step was the `Skill` tool call, so the
skill is reliably discovered and invoked. Step 3 of the trajectory is a `user`-source
message containing the full SKILL.md body ("Base directory for this skill: …").

### 2. Does every attempt get a clean environment?

Yes. Each trial is a fresh container from the task image. Verified: all three
downloaded workspaces have exactly one commit (`eb4bee9 baseline`, identical hash),
and each trial's changes were only its own. With `--n-concurrent 3` the trials ran
in parallel with no cross-contamination.

The baseline is created **in the Dockerfile** (`git init && git add -A && git commit`),
so the image itself carries the reference state; no per-trial setup step is needed.

### 3. How to preserve the complete final repo

`[[artifacts]] source = "/app"` in `task.toml` (or `--artifact /app` on the CLI).
After the agent finishes Harbor tars the directory out of the container and mirrors
it at `<trial>/artifacts/app/` (absolute container path → relative host path).
`exclude = [...]` passes `tar --exclude` patterns; the spike excludes
`node_modules`, `__pycache__`, `.pytest_cache`, `.venv`.

`<trial>/artifacts/manifest.json` records each entry with `status` (`ok` / `empty`).
The download includes `.git`, so the baseline commit travels with the workspace.

### 4. Can Harbor capture a patch/diff directly?

Not as a first-class feature (`harbor run -h` has no diff option; `[[verifier.collect]]`
can run a command before artifact collection but is tied to the verifier phase, which
we disable). Skill Lab computes it on the host, which is cleaner anyway:

```
git -C <trial>/artifacts/app status --porcelain --untracked-files=all   # created/modified/deleted
GIT_INDEX_FILE=<abs>/.git/skill-lab-index git add -A                     # scratch index so untracked files appear
git diff --cached --numstat HEAD                                         # stats
git diff --cached --binary HEAD                                          # patch
```

The scratch index leaves the downloaded workspace's real index untouched.
(`GIT_INDEX_FILE` must be absolute — relative paths resolve against the worktree and
fail with `-C`.)

### 5. What is in ATIF trajectories for Claude Code?

`<trial>/agent/trajectory.json`, `schema_version: "ATIF-v1.7"` (converted from the
native session JSONL that is also retained at `<trial>/agent/sessions/`). Contents:

- `agent`: `{name: "claude-code", version: "2.1.270", model_name: "claude-sonnet-5", extra: {cwds, git_branches}}`
- `steps[]`: `step_id`, `timestamp`, `source` (`user`/`agent`), `message` (string),
  `model_name`, `tool_calls[]` (`tool_call_id`, `function_name`, `arguments` — full
  args, e.g. the Bash `command`, Read `file_path`, Write `content`), `observation.results[]`
  (`source_call_id`, `content` = the tool output, e.g. file contents / command stdout),
  per-step `metrics` (`prompt_tokens`, `completion_tokens`, `cached_tokens`, `cost_usd`,
  plus `extra` with cache creation/read tokens, thinking tokens, `cost_source: litellm_estimate`).
- `final_metrics`: `total_prompt_tokens`, `total_completion_tokens`, `total_cached_tokens`,
  `total_cost_usd`, `total_steps`.

Tool names are Claude Code's own (`Skill`, `Bash`, `Read`, `Write`, `Edit`, `Glob`, …).
Claude Code batches parallel tool calls into a single step (one step had 9 `Read`
calls). The final response is the last `agent` step's `message`.

This is more than enough evidence for the per-run summarizer. Observation `content`
can be large (full file reads) — the summarizer should truncate.

### 6. Is the skill digest in the output?

Yes: `<trial>/lock.json` → `skills[]` with `{name, source, digest}` where digest is
`sha256:` over sorted `(relative_path, sha256(content))` pairs
(`harbor/skills.py::compute_skill_digest`). It is identical across trials of a job.
The job-level `lock.json` does **not** contain it (it holds per-trial lock entries
under `trials`). Skill Lab can use Harbor's digest directly in `experiment.yaml`
rather than recomputing.

`<trial>/result.json` → `agent_info.version` (Claude Code version) and
`agent_info.model_info.name` are also available for the manifest.

### 7. Python API vs. CLI

Shell out to the CLI for V1. `harbor run` is a stable documented surface with a
`--dry-run` validator and `--print-config`, and the job dir layout is simple. The
Python API (`harbor.job.Job`, `harbor.models.job.config.JobConfig`) exists but pulls in
a large dependency tree and its constructor signatures are internal. Revisit if we
need progress events.

### 8. Crashes / timeouts

Probed with `--agent-timeout 15`. Harbor:
- writes `result.json` with `exception_info = {exception_type, exception_message:
  "Agent execution timed out after 15.0 seconds", exception_traceback, occurred_at}`
  and `agent_execution` timing;
- **still** writes the partial `trajectory.json` (15 tool calls, tokens, cost) and
  **still** downloads `/app` (unchanged in this case);
- exits `harbor run` with status 0 and counts the trial under "Exceptions".

So `completed = exception_info is None` and partial evidence remains usable for
analysis (e.g. "3 runs timed out while still reading files").

### 9. Token / cost fields

`result.json` → `agent_result.{n_input_tokens, n_cache_tokens, n_output_tokens, cost_usd}`.
Same totals in `trajectory.json.final_metrics`. Note `n_input_tokens` is the
sum of prompt tokens across LLM calls (~176k here) and mostly cache reads
(`total_cached_tokens` ≈ 162k); cost is a litellm estimate (~$0.09/run).

Timing: `result.json` → `agent_execution.{started_at, finished_at}` (also
`environment_setup`, `agent_setup`, `started_at`, `finished_at` for the trial).

### 10. How much data does Harbor retain by default?

Per trial (~1 MB for this fixture): `agent/trajectory.json`, `agent/sessions/`
(native Claude JSONL, skills copy, settings), `agent/claude-code.txt` (stdout),
`agent/setup/` (install logs), `artifacts/` (whatever we declared), `config.json`,
`lock.json`, `result.json`, `trial.log`. The container is deleted after the trial
(`--delete` default). Nothing else is kept, so `[[artifacts]]` is the only way to
get the workspace.

### 11. Can a trial reference its baseline repo state?

Yes via the baseline commit baked into the image: `git rev-parse HEAD` in any
downloaded workspace (`eb4bee9`) identifies it, and `git diff HEAD` is the change.
The experiment manifest should also record the fixture's source path and, if it is
a git repo, its commit — Harbor does not know about the fixture's origin.

### 12. Harbor version to pin

`harbor==0.23.0`. Task `schema_version = "1.4"`, trajectories `ATIF-v1.7`.

## Trial directory layout (observed)

```
<jobs-dir>/<job-name>/
├── config.json
├── lock.json
├── result.json                 # job stats only
├── job.log
└── task__<7-char id>/          # one per attempt
    ├── agent/
    │   ├── trajectory.json     # ATIF
    │   ├── claude-code.txt
    │   ├── sessions/           # native Claude Code state
    │   └── setup/
    ├── artifacts/
    │   ├── manifest.json
    │   ├── app/                # our workspace, incl. .git
    │   └── logs/artifacts/     # convention dir (empty)
    ├── verifier/               # empty (disabled)
    ├── config.json
    ├── lock.json               # skills[] with digest
    ├── result.json             # TrialResult
    └── trial.log
```

Trial dir names are `<task-name>__<short-uuid>`; sort order is not run order.
Use `result.json.started_at` to order runs.

## Things to carry into Phase 1

- Validate skill dir name vs. frontmatter `name`.
- Order runs by `started_at`, not directory name.
- `run.json` should reference `<trial>/agent/trajectory.json` and
  `<trial>/artifacts/app` rather than copying them.
- Add a `.dockerignore`-style exclude list for fixture copying (currently hardcoded).
- The three spike runs behaved almost identically (all updated the stale doc in
  place, 16 tool calls each). The example skill/fixture may need to be less
  trivial before cross-run analysis has anything interesting to say — or run at
  N=20 and see.
