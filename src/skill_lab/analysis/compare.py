"""Compare two experiments: same repo/prompt/agent, different skill version (§17)."""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from skill_lab.analysis.analyze_runs import facts_table
from skill_lab.analysis.model import AnalysisModel
from skill_lab.analysis.summarize_run import load_prompt, load_summaries, skill_md_for
from skill_lab.experiment import load_runs
from skill_lab.models.analysis import Analysis
from skill_lab.models.comparison import COMPARISON_SCHEMA, BehaviorFrequency, Comparison
from skill_lab.models.experiment import ExperimentPaths, Manifest
from skill_lab.models.run_record import RunRecord
from skill_lab.models.run_summary import RunSummary


@dataclass
class ExperimentBundle:
    """Everything the comparator needs from one experiment, loaded once."""

    paths: ExperimentPaths
    manifest: Manifest
    skill_md: str
    records: list[RunRecord]
    summaries: list[RunSummary]
    analysis: Analysis | None

    @classmethod
    def load(cls, paths: ExperimentPaths) -> "ExperimentBundle":
        manifest = Manifest.load(paths.manifest)
        records = load_runs(paths)
        summaries = load_summaries(paths)
        have = {s.run_id for s in summaries}
        missing = [r.run_id for r in records if r.run_id not in have]
        if missing:
            raise ValueError(f"{manifest.id}: runs without summaries {missing}; run `skill-lab analyze {manifest.id}`")
        analysis = Analysis.load(paths.analysis) if paths.analysis.exists() else None
        return cls(paths, manifest, skill_md_for(paths, manifest), records, summaries, analysis)


def compatibility_warnings(a: Manifest, b: Manifest) -> list[str]:
    """Things that differ besides the skill, which would confound the comparison."""
    warnings = []
    if a.prompt["text"].strip() != b.prompt["text"].strip():
        warnings.append("prompts differ")
    if a.prompt.get("persona_digest") != b.prompt.get("persona_digest"):
        warnings.append("simulated-user personas differ")
    if bool(a.agent.get("interactive")) != bool(b.agent.get("interactive")):
        warnings.append("one experiment is interactive and the other is not")
    a_repo, b_repo = a.repository.get("digest"), b.repository.get("digest")
    if a_repo is None or b_repo is None:
        # Experiments created before fixture digests existed; fall back to the
        # (coarser) enclosing-repo commit.
        a_repo, b_repo = a.repository.get("git_commit"), b.repository.get("git_commit")
    if a_repo != b_repo or a.repository.get("source") != b.repository.get("source"):
        warnings.append(f"repository fixture differs ({a.repository.get('source')} {str(a_repo)[:15]} vs "
                        f"{b.repository.get('source')} {str(b_repo)[:15]})")
    if a.agent.get("name") != b.agent.get("name") or a.agent.get("model") != b.agent.get("model"):
        warnings.append(f"agent/model differs ({a.agent.get('name')}/{a.agent.get('model')} vs {b.agent.get('name')}/{b.agent.get('model')})")
    if a.skill["digest"] == b.skill["digest"]:
        warnings.append("skill digests are identical; this compares two samples of the same skill")
    return warnings


def skill_diff(a: ExperimentBundle, b: ExperimentBundle) -> str:
    return "".join(difflib.unified_diff(
        a.skill_md.splitlines(keepends=True), b.skill_md.splitlines(keepends=True),
        fromfile=f"{a.manifest.id}/SKILL.md", tofile=f"{b.manifest.id}/SKILL.md",
    ))


def _analysis_block(label: str, bundle: ExperimentBundle) -> list[str]:
    a = bundle.analysis
    if a is None:
        return [f"## {label}: no cross-run analysis available", ""]
    lines = [f"## {label}: cross-run analysis", a.overview, "", "strategies:"]
    lines += [f"  - {c.name} ({len(c.run_ids)} runs: {', '.join(c.run_ids)}): {c.description}" for c in a.clusters]
    lines.append("recurring problems:")
    lines += [f"  - {f.title} ({', '.join(f.run_ids)}): {f.description}" for f in a.recurring_problems] or ["  (none)"]
    lines.append("strong runs: " + (", ".join(s.run_id for s in a.strong_runs) or "(none)"))
    return lines + [""]


def _summaries_block(label: str, bundle: ExperimentBundle) -> list[str]:
    lines = [f"## {label}: per-run summaries"]
    for s in bundle.summaries:
        lines += [f"### {label} run {s.run_id}", f"approach: {s.approach}", f"outcome: {s.outcome}"]
        if s.notable_behaviors:
            lines += ["notable: " + " | ".join(s.notable_behaviors)]
        if s.possible_problems:
            lines += ["problems: " + " | ".join(s.possible_problems)]
    return lines + [""]


def build_comparison_input(a: ExperimentBundle, b: ExperimentBundle, diff: str) -> str:
    parts = [
        "# Task prompt / simulated-user persona (same in both experiments)",
        (a.manifest.prompt.get("persona") or a.manifest.prompt["text"]).strip(),
        "",
        f"# Experiment A: {a.manifest.id} ({len(a.records)} runs)",
        "## A: SKILL.md",
        a.skill_md.strip(),
        "",
        f"# Experiment B: {b.manifest.id} ({len(b.records)} runs)",
        "## B: SKILL.md",
        b.skill_md.strip(),
        "",
        "# SKILL.md diff (A -> B)",
        diff.strip() or "(no textual difference)",
        "",
        *_analysis_block("A", a),
        *_analysis_block("B", b),
        "## A: per-run facts",
        facts_table(a.records),
        "",
        "## B: per-run facts",
        facts_table(b.records),
        "",
        *_summaries_block("A", a),
        *_summaries_block("B", b),
    ]
    return "\n".join(parts)


def compare_experiments(a: ExperimentBundle, b: ExperimentBundle, model: AnalysisModel) -> Comparison:
    diff = skill_diff(a, b)
    text = build_comparison_input(a, b, diff)
    result = model.generate_json(
        system_prompt=load_prompt("compare-experiments"),
        prompt=text,
        schema=COMPARISON_SCHEMA,
    )
    a_known = {r.run_id for r in a.records}
    b_known = {r.run_id for r in b.records}
    behaviors = [
        BehaviorFrequency(x["behavior"], _ids(x["a_run_ids"], a_known), _ids(x["b_run_ids"], b_known))
        for x in result["behaviors"]
    ]
    return Comparison(
        a_id=a.manifest.id,
        b_id=b.manifest.id,
        a_run_count=len(a.records),
        b_run_count=len(b.records),
        a_skill_digest=a.manifest.skill["digest"],
        b_skill_digest=b.manifest.skill["digest"],
        skill_diff=diff,
        compatibility_warnings=compatibility_warnings(a.manifest, b.manifest),
        summary=result["summary"],
        behaviors=behaviors,
        consistency=dict(result["consistency"]),
        improvements=list(result["improvements"]),
        new_behaviors=list(result["new_behaviors"]),
        remaining_issues=list(result["remaining_issues"]),
        model=getattr(model, "model", None),
        input_chars=len(text),
    )


def _ids(run_ids: list[str], known: set[str]) -> list[str]:
    out: list[str] = []
    for rid in run_ids:
        digits = "".join(ch for ch in str(rid) if ch.isdigit())
        norm = digits.zfill(3) if digits else str(rid)
        if norm in known and norm not in out:
            out.append(norm)
    return sorted(out)
