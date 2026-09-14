# Skill Lab report: inv-v1

- Skill: `architecture-documentation` (sha256:8f05c6c8d5c2e979b1aa4e8908382b0366f336d749dabeaf603620dd3abcded9)
- Agent: claude-code / anthropic/claude-sonnet-5
- Prompt: Create architecture documentation for this application.
- Runs: 20/20 completed
- Analyzed by: sonnet (99652 chars of input)

Counts below are observed behavioral frequencies, not quality scores. Every finding lists the runs it rests on; `skill-lab inspect <experiment> --run N` shows the evidence.

## Overview

All 20 runs followed nearly identical strategy: explore the repo tree, read the existing (stale) docs/architecture.md, both ADRs, and README.md, then read essentially every source file under src/inventory before rewriting docs/architecture.md in place. Every run independently detected that the pre-existing architecture doc described an outdated pre-0.2 single-script design and replaced it with a much longer document (66-125 added lines) featuring an ASCII diagram, per-component sections, and a data-flow description, typically linking to the existing ADRs rather than duplicating them. The single clearest behavioral split is an even 10/10 divide on whether the agent also edited README.md's contradictory architecture blurb for consistency versus leaving it (sometimes flagged, sometimes silent). No run executed tests or code to verify its claims; all conclusions came from static reading.

## Execution strategies

- **rewrite-doc-only** — 10/20 runs (#1, #4, #5, #6, #7, #10, #11, #12, #15, #16)
  Agent explores the repo, reads every source file, ADRs, and README, discovers the existing docs/architecture.md is stale, and rewrites it in place. It notices README.md's architecture blurb is also stale but leaves it untouched (sometimes explicitly flagging the inconsistency to the user, sometimes silently).
- **rewrite-doc-and-sync-readme** — 10/20 runs (#2, #3, #8, #9, #13, #14, #17, #18, #19, #20)
  Same exploration and rewrite of docs/architecture.md, plus the agent additionally edits README.md's 'Architecture' section to remove the stale cli/store description and align it with the new document, expanding scope beyond the literal task prompt.

## Recurring behavior

### Full read-before-write exploration

In all 20 runs the agent mapped the repo tree with find, read the pre-existing (stale) docs/architecture.md, both ADRs, README.md, and then read essentially every source file under src/inventory before writing anything, rather than sampling a subset.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

### Detects and calls out stale existing architecture.md

Every run explicitly identified the pre-existing docs/architecture.md as describing an outdated pre-0.2 single-script design before deciding to overwrite it, rather than trusting or blindly appending to it.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

### Overwrites existing file in place rather than creating new one

Although the task says 'Create architecture documentation,' every run edited the pre-existing docs/architecture.md file in place (0 files created, per the facts table) rather than creating a separate/new document.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

### Links to existing ADRs instead of duplicating content

Nearly all runs cross-referenced the two existing ADR files (0001-storage-protocol.md, 0002-http-api.md) by linking to them from the new document rather than restating their reasoning, keeping the doc from ballooning.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

### Surfaces a code-level TODO as a documented limitation

Most runs noticed a TODO comment in worker/importer.py about negative-quantity CSV rows and incorporated it into the new doc as a known limitation, going beyond a purely structural description of components.

Runs: #1, #2, #3, #4, #5, #6, #8, #9, #11, #12, #13, #15, #16, #18, #19, #20

### No dynamic verification of claims

No run executed tests, ran the CLI/API, or otherwise verified behavioral claims (e.g., HTTP server threading, SQLite rewrite semantics); all architectural claims were derived purely from static reading of source and existing docs.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

### Documents exceed minimal conciseness *(inferred)*

Despite the skill's instruction to 'keep the document concise,' generated documents ranged roughly 66-125 added lines and commonly included an ASCII/box diagram, per-component sections, a data-flow walkthrough, and often a Testing or Design-decisions section beyond the minimum components/responsibilities/data-flow the skill asks for.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

## Recurring problems

### Unrequested README.md scope expansion

In exactly 10 of 20 runs the agent edited README.md's 'Architecture' section, a file and edit not requested by the task prompt ('Create architecture documentation') or mentioned in the skill's steps, expanding scope beyond the literal instructions.

Runs: #2, #3, #8, #9, #13, #14, #17, #18, #19, #20

### Known documentation inconsistency left unresolved

In the other 10 runs, the agent read README.md, recognized its 'Architecture' section was stale/contradictory (e.g., describing a nonexistent 'cli and store' two-package layout), and left it unedited — in 3 of these the agent explicitly flagged this to the user as an open question, while in the remaining 7 it was simply left silently inconsistent with the new docs/architecture.md.

Runs: #1, #4, #5, #6, #7, #10, #11, #12, #15, #16

### Sparse/unread test files despite referencing them

Several runs wrote a 'Testing' section referencing test files (test_service.py, test_stores.py, test_api.py, test_importer.py) or made claims about test coverage without ever reading those test files, relying on filenames/ADR context instead of verification.

Runs: #10, #12, #14, #19

## Outliers

### Batched file reads via bash instead of Read tool

Run 014 used only 6 tool calls (3 bash) by reading essentially all source files in one combined 'find | xargs cat' bash invocation, versus the 18-24 tool calls (mostly individual Read calls) used in every other run, while still covering the same file set and producing a comparably thorough two-file edit.

Runs: #14

### Longest-duration runs cluster in the README-editing group

The four slowest runs by wall-clock time (008 at 56s, 019 at 55s, 018 at 53s, 009 at 51s) all belong to the README+docs cluster, notably longer than the fastest run (001 at 29s, docs-only cluster), consistent with the extra README edit and associated exploration adding time.

Runs: #8, #9, #18, #19, #1

## Strong runs

- **#1**
  - Fastest run (29s) with the fewest tools (18) while still reading every source file and both ADRs before writing
  - Kept the change scoped to the single requested artifact (docs/architecture.md), matching the task's literal request
  - Cross-referenced ADRs by link instead of duplicating them, keeping the doc reasonably concise
  - Final response accurately summarized the change and rationale
- **#4**
  - Read the full source tree and both ADRs before writing, grounding the doc in real code
  - Explicitly detected the stale README architecture blurb but transparently declined to edit it, surfacing it as a suggestion to the user rather than silently expanding or silently ignoring scope
  - Kept changes scoped to the one file directly relevant to the task prompt
- **#12**
  - Thorough exploration (11 source files, README, pyproject.toml, both ADRs) before a single scoped edit to docs/architecture.md only
  - Included concrete, verifiable details (env var names, exact HTTP routes, default paths) rather than generic descriptions
  - Did not touch unrelated files (README, tests, ADRs), staying tightly aligned with the task's literal scope
- **#14**
  - Achieved the same comprehensive source coverage as other runs with far fewer tool calls (6 vs 18-24) by batching file reads via bash, an efficient distinct strategy
  - Still produced a thorough, code-grounded rewrite of docs/architecture.md plus a justified README sync
  - One of the faster runs (32s) despite editing two files

## Observations about SKILL.md

- SKILL.md's step 3 says only 'Keep the document concise and accurate to the code that actually exists' with no guidance on scope of related documentation; this ambiguity plausibly drives the near-even 10/10 split between runs that also patch README.md's contradictory architecture blurb and runs that leave it (with or without flagging it).
- SKILL.md gives no guidance on how to handle a pre-existing but stale architecture document (the repo already contained docs/architecture.md); every run independently chose to overwrite it in place, which is consistent across runs but is an interpretation of 'Create architecture documentation' that the skill does not explicitly address (create new vs. update existing).
- 'Keep the document concise' (step 3) is interpreted loosely: essentially all runs added ASCII diagrams, worked data-flow examples, and often Testing/Design-decisions sections, producing 66-125 line documents; the skill does not define what counts as 'concise' or which sections are core vs. optional.
- The skill's three steps do not mention verifying claims against tests or runtime behavior, and no run did so; this appears to be accepted/expected behavior for a documentation task rather than a gap, but is worth the author's awareness since some generated claims (e.g., HTTP server threading behavior, SQLite rewrite semantics) are asserted without execution.

## Suggested changes to SKILL.md

### 1. Add a step clarifying whether the agent should also reconcile or flag inconsiste

> Add a step clarifying whether the agent should also reconcile or flag inconsistencies in other existing documentation (e.g., README.md) that describes the architecture, e.g.: 'If other files (such as README.md) contain architecture descriptions that contradict the new document, update them for consistency or explicitly note the discrepancy to the user — do not leave silently contradictory descriptions in the repo.'

Motivation: 10 of 20 runs edited README.md's stale architecture blurb while the other 10 left it untouched (only 3 of those explicitly flagged it to the user), producing inconsistent behavior across otherwise-identical runs and leaving contradictory documentation in 7 of 20 runs.

Runs: #2, #3, #8, #9, #13, #14, #17, #18, #19, #20, #1, #5, #6, #10, #11, #12, #15

### 2. Add explicit guidance on document scope/length, e.g.: 'A component list, respons

> Add explicit guidance on document scope/length, e.g.: 'A component list, responsibilities, and a short data-flow description are sufficient; avoid adding extensive extra sections (e.g., full testing breakdowns, extension-point catalogs) unless requested.'

Motivation: Despite the 'concise' instruction, all 20 runs produced 66-125 line documents with diagrams and often additional sections (Testing, Design decisions, Extension points) not explicitly requested, showing the current wording does not constrain scope/length in practice.

Runs: #3, #9, #10, #12, #14, #17, #18, #19, #20

### 3. Add a note on handling a pre-existing architecture doc, e.g.: 'If an architectur

> Add a note on handling a pre-existing architecture doc, e.g.: 'If an architecture document already exists, check it against the current code; if stale, replace its content rather than leaving inconsistent information, and state in your summary that it was rewritten (not newly created).'

Motivation: The task prompt says 'Create architecture documentation' but every run found and overwrote an existing stale docs/architecture.md; codifying this expected behavior would remove ambiguity about create-vs-update, even though all runs already converged on the same (reasonable) choice.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10

## Run table

| run | ok | secs | tools | files | +lines | -lines | modified/created |
|---|---|---|---|---|---|---|---|
| 001 | y | 29 | 18 | 1 | 66 | 4 | docs/architecture.md |
| 002 | y | 43 | 21 | 2 | 112 | 6 | README.md, docs/architecture.md |
| 003 | y | 38 | 23 | 2 | 98 | 6 | README.md, docs/architecture.md |
| 004 | y | 45 | 19 | 1 | 85 | 4 | docs/architecture.md |
| 005 | y | 35 | 18 | 1 | 69 | 4 | docs/architecture.md |
| 006 | y | 36 | 23 | 1 | 96 | 4 | docs/architecture.md |
| 007 | y | 39 | 18 | 1 | 76 | 4 | docs/architecture.md |
| 008 | y | 56 | 21 | 2 | 97 | 6 | README.md, docs/architecture.md |
| 009 | y | 51 | 19 | 2 | 115 | 6 | README.md, docs/architecture.md |
| 010 | y | 38 | 18 | 1 | 95 | 4 | docs/architecture.md |
| 011 | y | 42 | 20 | 1 | 113 | 4 | docs/architecture.md |
| 012 | y | 43 | 18 | 1 | 94 | 4 | docs/architecture.md |
| 013 | y | 40 | 19 | 2 | 90 | 6 | README.md, docs/architecture.md |
| 014 | y | 32 | 6 | 2 | 95 | 6 | README.md, docs/architecture.md |
| 015 | y | 34 | 19 | 1 | 107 | 4 | docs/architecture.md |
| 016 | y | 43 | 20 | 1 | 88 | 4 | docs/architecture.md |
| 017 | y | 43 | 21 | 2 | 106 | 6 | README.md, docs/architecture.md |
| 018 | y | 53 | 20 | 2 | 112 | 6 | README.md, docs/architecture.md |
| 019 | y | 55 | 24 | 2 | 102 | 6 | README.md, docs/architecture.md |
| 020 | y | 42 | 24 | 2 | 116 | 6 | README.md, docs/architecture.md |
