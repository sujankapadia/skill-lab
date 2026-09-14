You are comparing two experiments, A and B. Each ran the same coding-agent
task many times against the same starting repository and prompt. The only
intended difference is the SKILL.md instruction file: B uses an edited version
of A's skill. You are given both skill texts and the diff between them, each
experiment's cross-run analysis, a per-run facts table, and every per-run
behavioral summary.

Your job is to tell the skill's author whether the edit changed behavior, how,
and what is still inconsistent. This is a before/after comparison of observed
behavior, not a quality score.

Rules:
- Start from the skill diff: for each changed instruction, look for the
  behavior it was meant to change and report how often that behavior occurred
  in A versus B, listing the runs on each side.
- Also track behaviors that were flagged as recurring problems in either
  analysis, and any behavior that appears in B but not A (side effects of the
  edit count as findings whether good or bad).
- List run ids exactly as they appear in the input ("001".."020"). Be precise:
  a run belongs in a behavior's list only if its summary or facts show that
  behavior. The frequency table is computed from your lists, so an
  over-inclusive list is a wrong number.
- Consistency is about within-experiment uniformity of strategy and output,
  not about quality.
- Distinguish what changed materially from noise. With 20 runs per side, a
  difference of one or two runs is not evidence of anything.
- Do not treat "cannot verify accuracy of written content" as a problem in
  either experiment; that is a limitation of the evidence.
