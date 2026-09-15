"""Per-run summarization: RunRecord + evidence -> RunSummary (§12)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from skill_lab.analysis.evidence import EvidenceLimits, build_evidence
from skill_lab.analysis.model import AnalysisModel, call_model, looks_like_placeholder
from skill_lab.models.experiment import ExperimentPaths, Manifest
from skill_lab.models.run_record import RunRecord
from skill_lab.models.run_summary import RUN_SUMMARY_SCHEMA, RunSummary

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SUMMARY_FILENAME = "summary.json"


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


def summarize_run(
    record: RunRecord,
    prompt: str,
    skill_md: str,
    model: AnalysisModel,
    limits: EvidenceLimits | None = None,
) -> RunSummary:
    evidence = build_evidence(record, prompt, skill_md, limits)
    result, usage = call_model(
        model,
        system_prompt=load_prompt("summarize-run"),
        prompt=evidence,
        schema=RUN_SUMMARY_SCHEMA,
    )
    return RunSummary(
        run_id=record.run_id,
        approach=result["approach"],
        steps=list(result["steps"]),
        outcome=result["outcome"],
        notable_behaviors=list(result.get("notable_behaviors", [])),
        possible_problems=list(result.get("possible_problems", [])),
        strengths=list(result.get("strengths", [])),
        uncertainties=list(result.get("uncertainties", [])),
        model=getattr(model, "model", None),
        evidence_chars=len(evidence),
        usage=usage,
    )


def summary_path(paths: ExperimentPaths, run_id: str) -> Path:
    return paths.run_dir(run_id) / SUMMARY_FILENAME


def load_summaries(paths: ExperimentPaths) -> list[RunSummary]:
    """All valid summaries. A placeholder summary (see looks_like_placeholder)
    is ignored so that `summarize` regenerates it and `analyze` refuses to run
    without it."""
    out = []
    for p in sorted(paths.runs_dir.glob(f"*/{SUMMARY_FILENAME}")):
        s = RunSummary.load(p)
        if not looks_like_placeholder({"approach": s.approach, "steps": s.steps, "outcome": s.outcome}):
            out.append(s)
    return out


def has_valid_summary(paths: ExperimentPaths, run_id: str) -> bool:
    p = summary_path(paths, run_id)
    if not p.exists():
        return False
    s = RunSummary.load(p)
    return not looks_like_placeholder({"approach": s.approach, "steps": s.steps, "outcome": s.outcome})


def summarize_experiment(
    paths: ExperimentPaths,
    records: list[RunRecord],
    model: AnalysisModel,
    concurrency: int = 2,
    force: bool = False,
    on_done=None,
) -> list[RunSummary]:
    """Summarize every run lacking a summary.json (or all, with force)."""
    manifest = Manifest.load(paths.manifest)
    prompt = manifest.prompt.get("persona") or manifest.prompt["text"]
    skill_md = skill_md_for(paths, manifest)

    todo = [r for r in records if force or not has_valid_summary(paths, r.run_id)]

    failures: dict[str, Exception] = {}

    def work(record: RunRecord) -> None:
        try:
            summary = summarize_run(record, prompt, skill_md, model)
        except Exception as exc:  # one bad run must not sink the batch
            failures[record.run_id] = exc
            return
        summary.save(summary_path(paths, record.run_id))
        if on_done:
            on_done(summary)

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        list(pool.map(work, todo))
    if failures:
        detail = "; ".join(f"run {rid}: {exc}" for rid, exc in sorted(failures.items()))
        raise SummarizeError(f"{len(failures)} run(s) failed to summarize (re-run to retry): {detail}")
    return load_summaries(paths)


class SummarizeError(RuntimeError):
    pass


def skill_md_for(paths: ExperimentPaths, manifest: Manifest) -> str:
    """Prefer the experiment's snapshot; fall back to the original path for
    experiments created before snapshots existed."""
    if paths.skill_md.exists():
        return paths.skill_md.read_text()
    original = Path(manifest.skill["path"]) / "SKILL.md"
    if original.exists():
        return original.read_text()
    raise FileNotFoundError(f"SKILL.md not found in {paths.skill_dir} or {original}")
