# Skill Lab comparison: inv-v1 → inv-v2

- A: `inv-v1` — 20 runs, skill sha256:8f05c6c8d5c2e979b1aa4e8908382b0366f336d749dabeaf603620dd3abcded9
- B: `inv-v2` — 20 runs, skill sha256:d5b6a84b77d98b229590a7d65b40b4b42c46b9c020736003a418c32bc4d624ef
- Compared by: sonnet (113976 chars of input)

Numbers are observed behavioral frequencies (runs exhibiting the behavior), not quality scores.

## Summary

The B skill edit added an explicit discovery step (check docs/, README, CONTRIBUTING, ADRs), a length target (~80 lines), an instruction to fix contradicting descriptions elsewhere in the repo, and a final-message reporting requirement. All four changes visibly took effect: README.md's stale architecture blurb, fixed in only 10/20 A runs, was fixed in all 20 B runs; CONTRIBUTING.md, essentially unread in A, was read in 17/20 B runs; document length dropped from a 66-125 added-line range in A to a tighter 49-84 range in B, mostly within the suggested budget; and every B run's final message enumerated rewritten vs. created files as newly required. Consistency across runs increased markedly in B (high vs. medium in A), since the even 10/10 strategy split in A around README-editing disappeared entirely. Remaining gaps in B are minor: 3/20 runs still skip CONTRIBUTING.md, a few docs still sit at the edge of the 80-line guidance, and cosmetic ASCII-diagram alignment issues persist in both experiments at similar rates. Overall the edit had its intended effect with no material negative side effects observed.

## Behavior frequencies

| Observation | inv-v1 | inv-v2 |
|---|---|---|
| Checked CONTRIBUTING.md for documentation-location conventions before writing | 0/20 | 17/20 |
| Skipped reading CONTRIBUTING.md despite it appearing in directory listing | 2/20 | 3/20 |
| Proactively edited README.md's stale 'Architecture' section for consistency with the new doc | 10/20 | 20/20 |
| Noticed README.md's architecture blurb was stale/contradictory but left it unedited (sometimes flagging it, sometimes silently) | 10/20 | 0/20 |
| Wrote a 'Testing' section referencing test files without having read those test files | 4/20 | 0/20 |
| Final message explicitly enumerated which files were rewritten vs. created | 0/20 | 20/20 |
| Produced a markedly long/verbose document (well beyond ~80 lines of new content, often 90-125 added lines) with extra sections like Testing/Extension points | 12/20 | 0/20 |
| Produced a document at or near the skill's ~80-line guidance (roughly 49-72 added lines, or explicitly flagged as close to/at the 80-line edge) | 0/20 | 17/20 |
| Final document length flagged as at or plausibly over the 80-line guidance once diagram counted | 0/20 | 3/20 |
| Rewrote existing stale docs/architecture.md in place rather than creating a duplicate document | 20/20 | 20/20 |
| Linked to existing ADRs instead of restating their content | 20/20 | 20/20 |
| ASCII diagram had minor alignment/rendering flaws (cosmetic issue) | 8/20 | 7/20 |
| Did not run tests or execute code to verify documentation claims (static reading only) | 20/20 | 20/20 |
| Did not modify any source code files | 20/20 | 20/20 |

<details><summary>Run ids per behavior</summary>

- Checked CONTRIBUTING.md for documentation-location conventions before writing: A —; B #1, #2, #3, #4, #5, #6, #7, #8, #11, #13, #14, #15, #16, #17, #18, #19, #20
- Skipped reading CONTRIBUTING.md despite it appearing in directory listing: A #1, #17; B #9, #10, #12
- Proactively edited README.md's stale 'Architecture' section for consistency with the new doc: A #2, #3, #8, #9, #13, #14, #17, #18, #19, #20; B #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20
- Noticed README.md's architecture blurb was stale/contradictory but left it unedited (sometimes flagging it, sometimes silently): A #1, #4, #5, #6, #7, #10, #11, #12, #15, #16; B —
- Wrote a 'Testing' section referencing test files without having read those test files: A #10, #12, #14, #19; B —
- Final message explicitly enumerated which files were rewritten vs. created: A —; B #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20
- Produced a markedly long/verbose document (well beyond ~80 lines of new content, often 90-125 added lines) with extra sections like Testing/Extension points: A #2, #3, #6, #9, #10, #11, #12, #15, #17, #18, #19, #20; B —
- Produced a document at or near the skill's ~80-line guidance (roughly 49-72 added lines, or explicitly flagged as close to/at the 80-line edge): A —; B #1, #2, #3, #4, #5, #6, #7, #8, #9, #11, #12, #13, #14, #15, #16, #18, #19
- Final document length flagged as at or plausibly over the 80-line guidance once diagram counted: A —; B #10, #17, #20
- Rewrote existing stale docs/architecture.md in place rather than creating a duplicate document: A #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20; B #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20
- Linked to existing ADRs instead of restating their content: A #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20; B #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20
- ASCII diagram had minor alignment/rendering flaws (cosmetic issue): A #1, #6, #9, #11, #15, #16, #18, #19; B #3, #5, #7, #13, #16, #17, #19
- Did not run tests or execute code to verify documentation claims (static reading only): A #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20; B #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20
- Did not modify any source code files: A #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20; B #1, #2, #3, #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16, #17, #18, #19, #20

</details>

## Behavior consistency

- inv-v1: medium: all 20 runs used the same read-everything-then-rewrite-in-place strategy and produced similar-shaped documents, but the cohort split evenly 10/10 on whether to also fix README.md's contradicting section, and document length varied widely (66-125 added lines).
- inv-v2: high: all 20 runs used the same discover-then-verify-then-rewrite strategy, all 20 fixed README.md, all 20 reported files touched in the final message, and document lengths clustered much more tightly (49-84 added lines); the only notable split is 17/20 vs 3/20 on reading CONTRIBUTING.md.

## Improvements

- README.md's stale 'Architecture' section, left uncorrected/inconsistently handled in 10 of 20 A runs, was fixed in all 20 B runs, directly resolving A's clearest recurring problem (an even 10/10 split with an unresolved documentation contradiction in half the runs).
- Document length dropped substantially and consolidated (A: 66-125 added lines across runs, often with extra sections like Testing/Extension points not requested; B: 49-84 added lines, generally hewing to the skill's ~80-line guidance), reflecting step 4's explicit length target.
- The 'Testing' section citing test files the agent never opened, a recurring accuracy problem in 4 A runs (010, 012, 014, 019), did not recur in any B run - likely a side effect of the tighter length/content guidance in step 4.
- CONTRIBUTING.md, effectively unread in A despite being visible in directory listings, was read in 17 of 20 B runs per the new explicit instruction in step 1, and its documentation-location convention was followed.
- All B runs' final messages explicitly stated which files were rewritten vs. created, matching new step 7; this reporting was not a distinguishing, consistently-produced behavior in A.

## New behavior in B

- Universal, unprompted README.md synchronization: every B run treated fixing README's contradicting text as part of the task, whereas in A this was a coin-flip (10/20) and the skill did not mention it at all.
- Reading CONTRIBUTING.md as part of the standard workflow: essentially absent in A, done in 17/20 B runs.
- Structured final-message reporting of rewritten vs. created files in 100% of B runs, an explicit new skill requirement (step 7) with no A equivalent.
- A new minority failure mode: 3 B runs (009, 010, 012) skip CONTRIBUTING.md even though the skill explicitly names it as a step-1 source to check, showing the instruction is not universally followed.
- Multiple B runs' summaries note the agent did not run tests despite CONTRIBUTING.md recommending it before changes - a new observation only possible because CONTRIBUTING.md is now being read, though not clearly a regression since this is a doc-only task.

## Remaining issues

- 3 of 20 B runs (009, 010, 012) still skip CONTRIBUTING.md despite the skill explicitly instructing to check it in step 1.
- A handful of B runs (010 at 84 lines/81 added, and 017, 020 flagged as close to or plausibly over budget once diagrams are counted) still push at or past the skill's 'roughly 80 lines' guidance.
- ASCII diagram alignment/rendering flaws persist as a minor cosmetic recurring issue in both A and B (e.g., B runs 003, 005, 007, 013, 016, 017, 019), unaddressed by the edit.
- No run in either experiment executes tests or code to verify documented behavioral claims (expected limitation, not a regression introduced by the edit).

## SKILL.md diff

```diff
--- inv-v1/SKILL.md
+++ inv-v2/SKILL.md
@@ -7,6 +7,21 @@
 
 When asked to document the architecture of a repository:
 
-1. Identify the main components of the application and how they interact.
-2. Write a Markdown document describing the components, their responsibilities, and the data flow between them.
-3. Keep the document concise and accurate to the code that actually exists.
+1. Find existing architecture documentation first. Check `docs/`, `README.md`,
+   `CONTRIBUTING.md`, and any ADRs, and note where the project says such
+   documentation should live.
+2. Identify the main components of the application and how they interact.
+3. If an architecture document already exists, check it against the current
+   code. If it is stale, rewrite it in place rather than creating a second
+   document. Otherwise create one in the location the project's conventions
+   indicate (default: `docs/architecture.md`).
+4. Write a Markdown document describing the components, their responsibilities,
+   and the data flow between them. Keep it to roughly 80 lines: a component
+   list, responsibilities, and a short data-flow description are sufficient.
+   Link to existing ADRs instead of restating them.
+5. Keep the document accurate to the code that actually exists.
+6. If other files (for example a README "Architecture" section) describe the
+   architecture in a way that now contradicts your document, update them so the
+   repository does not contain conflicting descriptions. Do not modify source
+   code for a documentation task.
+7. In your final message, say which files you rewrote and which you created.
```
