# Skill Lab report: inv-v2

- Skill: `architecture-documentation` (sha256:d5b6a84b77d98b229590a7d65b40b4b42c46b9c020736003a418c32bc4d624ef)
- Agent: claude-code / anthropic/claude-sonnet-5
- Prompt: Create architecture documentation for this application.
- Runs: 20/20 completed
- Analyzed by: sonnet (105288 chars of input)

Counts below are observed behavioral frequencies, not quality scores. Every finding lists the runs it rests on; `skill-lab inspect <experiment> --run N` shows the evidence.

## Overview

All 20 runs solved the task the same way: locate the existing stale docs/architecture.md (describing a pre-0.2 single-script design), read essentially every source file in src/inventory plus both ADRs, rewrite docs/architecture.md in place, and fix a matching stale 'Architecture' section in README.md. Every run touched exactly these two files, created nothing, deleted nothing, and left source code and ADRs untouched. The runs are unusually homogeneous in both outcome and process, differing mainly in (a) whether CONTRIBUTING.md was actually read (17/20 did, 3/20 skipped it), (b) final document length (49 to 84 added lines, with a few runs pushing past the skill's 'roughly 80 lines' guidance), and (c) whether the ASCII data-flow diagrams they chose to include rendered cleanly. No run modified source code or created a duplicate document, and every run's final message correctly enumerated which files were rewritten vs. updated, matching skill step 7.

## Execution strategies

- **full-discovery-rewrite-in-place** — 17/20 runs (#1, #2, #3, #4, #5, #6, #7, #8, #11, #13, #14, #15, #16, #17, #18, #19, #20)
  Agent reads docs/architecture.md, README.md, CONTRIBUTING.md, and both ADRs, reads every source file under src/inventory, determines the existing architecture.md is stale, rewrites it in place, fixes the contradicting README 'Architecture' section, links to ADRs instead of restating them, touches no source code, and reports exactly which files were rewritten/updated. This is the dominant strategy.
- **discovery-minus-contributing** — 3/20 runs (#9, #10, #12)
  Same overall strategy (read old doc, read all source, rewrite in place, fix README), but the agent never opened/read CONTRIBUTING.md even though it appeared in directory listings and the skill explicitly names it as a source of documentation-location conventions.

## Recurring behavior

### Exactly two files touched, nothing created or deleted

In all 20 runs the only files modified were docs/architecture.md (rewritten in place) and README.md (Architecture section edited); no new files were created and no files were deleted, and source code was never touched.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

### Read every source file before writing

Every run enumerated and read all files under src/inventory (typically 9-12 files: cli.py, config.py, service.py, storage/base.py + backends, api/server.py, worker/importer.py, __main__.py) before writing any documentation, rather than sampling a subset.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

### Detected staleness and rewrote in place rather than duplicating

All runs identified that docs/architecture.md described an obsolete pre-0.2 single-script design and rewrote it in place, per skill step 3, instead of creating a second document.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

### Proactively fixed the contradicting README Architecture section

Every run independently noticed that README.md's Architecture section described an outdated 'two packages: cli and store' model and rewrote it to match the new architecture.md, satisfying skill step 6, without being separately prompted to check README.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

### Linked to existing ADRs instead of restating them

All runs read the two existing ADRs (0001-storage-protocol, 0002-http-api) and linked to them from the new architecture.md rather than duplicating their content, per skill step 4.

Runs: #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

### No test execution or runtime verification

No run executed the test suite or the application to confirm the documented behavior; all conclusions were drawn from static reading of source files, even though CONTRIBUTING.md (where read) mentions running pytest before changes.

Runs: #1, #2, #3, #4, #6, #7, #8, #9, #11, #13, #17

### ASCII data-flow diagrams with alignment/formatting flaws

Roughly a third of runs added a hand-drawn ASCII box diagram to the data-flow section, and several of these had observable misalignment or malformed box-drawing characters (e.g. missing borders, uneven arrows).

Runs: #3, #5, #7, #13, #16, #17

## Recurring problems

### CONTRIBUTING.md skipped despite being explicitly named in the skill

3 of 20 runs (009, 010, 012) never opened CONTRIBUTING.md even though it appeared in their own directory listings and the skill's step 1 explicitly instructs checking CONTRIBUTING.md for conventions on where documentation should live. In these runs the agent relied only on docs/architecture.md, README.md, and ADRs to infer conventions.

Runs: #9, #10, #12

### Document length creeping toward or past the 'roughly 80 lines' guidance

Several runs produced documents at or beyond the skill's suggested ~80-line target once diagrams and multi-section content (Components, Data flow, Design decisions) are included. Run 010's summary explicitly states the final file reached 84 lines; runs 017 and 020 were also assessed as being close to or plausibly over the target once diagram lines are counted.

Runs: #10, #17, #20, #5, #15

## Outliers

### Longest resulting document, exceeding the 80-line guidance

Run 010 produced a docs/architecture.md explicitly described as 84 lines total (diff +81/-6), the largest of all 20 runs and the one most clearly exceeding the skill's 'roughly 80 lines' target; it also skipped reading CONTRIBUTING.md.

Runs: #10

### Longest runtime

Run 017 took 47 seconds, the longest of the 20 runs (range 27-47s), while producing one of the longer documents (+72 lines) with a diagram alignment issue noted.

Runs: #17

## Strong runs

- **#1**
  - Read every existing doc (README, CONTRIBUTING, both ADRs, old architecture.md) and every source file before writing anything
  - Produced a concise ~54-line rewritten doc, comfortably within the skill's 'roughly 80 lines' guidance
  - No diagram malformation or other formatting issue flagged in the summary
  - Correctly resolved the README contradiction and reported exactly which files were rewritten/updated, matching skill step 7
- **#6**
  - Completed the full discovery-verify-rewrite workflow (docs/, README, CONTRIBUTING, both ADRs, all 12 source files) in only 34 seconds/22 tool calls, among the more efficient thorough runs
  - Kept the rewritten doc to ~56 lines, well under the length guidance
  - Cited concrete code-level details (env var name, method signatures, HTTP endpoints) rather than vague generalities
  - No diagram malformation observed

## Observations about SKILL.md

- Step 1 ('Check docs/, README.md, CONTRIBUTING.md, and any ADRs') is not enforced structurally — 3 of 20 runs (009, 010, 012) saw CONTRIBUTING.md in a directory listing but never opened it, suggesting the instruction is treated as optional once other sources (README, old architecture.md) already seem to answer the question of where documentation lives.
- Step 4's guidance ('Keep it to roughly 80 lines... a component list, responsibilities, and a short data-flow description are sufficient') is soft enough that many runs interpreted 'short data-flow description' as license to add a multi-line ASCII box diagram in addition to prose, which both consumed line budget and introduced cosmetic alignment bugs in several runs (003, 005, 007, 013, 016, 017).
- Step 6 ('If other files... describe the architecture in a way that now contradicts your document, update them') was followed reliably in every run for README.md, suggesting this instruction is clear and easy to apply as written — no changes needed here.

## Suggested changes to SKILL.md

### 1. In step 1, make CONTRIBUTING.md a mandatory read rather than an implied one, e.g

> In step 1, make CONTRIBUTING.md a mandatory read rather than an implied one, e.g.: 'Open and read CONTRIBUTING.md if it exists — do not skip it even if README.md or an existing architecture doc already seems to answer where documentation lives.'

Motivation: 3 of 20 runs (009, 010, 012) never opened CONTRIBUTING.md despite it being listed in their own directory scans and named explicitly in the skill, relying only on other sources to infer doc-location conventions.

Runs: #9, #10, #12

### 2. Add explicit guidance on diagrams, e.g.: 'Prefer a short prose data-flow descrip

> Add explicit guidance on diagrams, e.g.: 'Prefer a short prose data-flow description over an ASCII box diagram; if you do include a diagram, keep it simple and double-check character alignment, since box-drawing diagrams are easy to render inconsistently.'

Motivation: 6+ of 20 runs (003, 005, 007, 013, 016, 017) added ASCII diagrams with observable alignment or border defects, and several runs' documents grew close to or past the 80-line target partly because of these diagrams (010, 017, 020).

Runs: #3, #5, #7, #13, #16, #17, #10, #20

## Run table

| run | ok | secs | tools | files | +lines | -lines | modified/created |
|---|---|---|---|---|---|---|---|
| 001 | y | 29 | 20 | 2 | 49 | 6 | README.md, docs/architecture.md |
| 002 | y | 32 | 21 | 2 | 58 | 6 | README.md, docs/architecture.md |
| 003 | y | 31 | 22 | 2 | 64 | 6 | README.md, docs/architecture.md |
| 004 | y | 38 | 22 | 2 | 58 | 6 | README.md, docs/architecture.md |
| 005 | y | 36 | 20 | 2 | 66 | 6 | README.md, docs/architecture.md |
| 006 | y | 34 | 22 | 2 | 53 | 6 | README.md, docs/architecture.md |
| 007 | y | 33 | 22 | 2 | 61 | 6 | README.md, docs/architecture.md |
| 008 | y | 29 | 21 | 2 | 53 | 6 | README.md, docs/architecture.md |
| 009 | y | 27 | 20 | 2 | 52 | 6 | README.md, docs/architecture.md |
| 010 | y | 43 | 21 | 2 | 81 | 6 | README.md, docs/architecture.md |
| 011 | y | 33 | 20 | 2 | 52 | 6 | README.md, docs/architecture.md |
| 012 | y | 39 | 21 | 2 | 68 | 6 | README.md, docs/architecture.md |
| 013 | y | 37 | 20 | 2 | 52 | 6 | README.md, docs/architecture.md |
| 014 | y | 30 | 20 | 2 | 65 | 6 | README.md, docs/architecture.md |
| 015 | y | 31 | 20 | 2 | 66 | 6 | README.md, docs/architecture.md |
| 016 | y | 37 | 22 | 2 | 53 | 6 | README.md, docs/architecture.md |
| 017 | y | 47 | 21 | 2 | 72 | 6 | README.md, docs/architecture.md |
| 018 | y | 35 | 21 | 2 | 62 | 6 | README.md, docs/architecture.md |
| 019 | y | 40 | 22 | 2 | 62 | 6 | README.md, docs/architecture.md |
| 020 | y | 34 | 20 | 2 | 69 | 6 | README.md, docs/architecture.md |
