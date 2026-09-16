"""skill-lab command-line interface."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from skill_lab.analysis.analyze_runs import analyze_runs
from skill_lab.analysis.compare import ExperimentBundle, compare_experiments
from skill_lab.analysis.model import ClaudeCliModel
from skill_lab.analysis.summarize_run import has_valid_summary, load_summaries, skill_md_for, summarize_experiment, summary_path
from skill_lab.experiment import DEFAULT_ROOT, load_runs, normalize_experiment, run_experiment
from skill_lab.models.experiment import ExperimentConfig, ExperimentPaths, Manifest
from skill_lab.models.run_summary import RunSummary
from skill_lab.reporting.markdown import frequency_table, render_comparison, render_report
from skill_lab.reporting.table import analysis_brief, experiment_header, run_detail, runs_table, summary_detail, usage_report


def _resolve_experiment(arg: str) -> ExperimentPaths:
    """Accept either an experiment directory or a bare experiment id."""
    path = Path(arg)
    if not path.is_dir():
        path = DEFAULT_ROOT / arg
    paths = ExperimentPaths(path)
    if not paths.manifest.exists():
        sys.exit(f"not an experiment directory (no experiment.yaml): {arg}")
    return paths


def cmd_run(args: argparse.Namespace) -> int:
    if args.interactive:
        if not args.persona_file:
            sys.exit("--interactive requires --persona-file (the simulated user's goal and answers)")
        persona = args.persona_file.read_text()
        prompt = args.prompt_file.read_text() if args.prompt_file else (args.prompt or persona.strip().splitlines()[0])
    else:
        if not (args.prompt or args.prompt_file):
            sys.exit("one of --prompt / --prompt-file is required")
        persona = None
        prompt = args.prompt_file.read_text() if args.prompt_file else args.prompt
    config = ExperimentConfig(
        id=args.name or datetime.now().strftime("exp-%Y%m%d-%H%M%S"),
        skill=args.skill,
        repo=args.repo,
        prompt=prompt,
        attempts=args.attempts,
        agent=args.agent,
        model=args.model,
        concurrency=args.concurrency,
        agent_timeout_sec=args.agent_timeout,
        auth=args.auth,
        claude_code_version=args.claude_code_version,
        apt_packages=args.apt or [],
        interactive=args.interactive,
        persona=persona,
        user_model=args.user_model,
    )
    paths = run_experiment(config, args.output)
    manifest = Manifest.load(paths.manifest)
    records = load_runs(paths)
    print()
    print(experiment_header(manifest, records))
    print(f"Harbor job: {paths.harbor_job_dir(manifest.harbor['job_name'])}")
    print()
    print(runs_table(records))
    if records and not args.no_analyze:
        print()
        _analyze(paths, records, args.analysis_model, args.analysis_concurrency, force=False)
    return 0 if records and all(r.completed for r in records) else 1


def _analyze(paths: ExperimentPaths, records, model_name: str, concurrency: int, force: bool) -> int:
    model = ClaudeCliModel(model=model_name)
    pending = [r for r in records if force or not has_valid_summary(paths, r.run_id)]
    if pending:
        print(f"Summarizing {len(pending)} run(s) with {model_name} (concurrency {concurrency})...", flush=True)
        summarize_experiment(
            paths, records, model, concurrency=concurrency, force=force,
            on_done=lambda s: print(f"  run {s.run_id}: {s.approach[:90]}", flush=True),
        )
    summaries = load_summaries(paths)
    manifest = Manifest.load(paths.manifest)
    print(f"Analyzing {len(records)} runs with {model_name}...", flush=True)
    task_text = manifest.prompt.get("persona") or manifest.prompt["text"]
    analysis = analyze_runs(manifest.id, task_text, skill_md_for(paths, manifest), records, summaries, model)
    analysis.save(paths.analysis)
    paths.report.write_text(render_report(manifest, records, analysis))
    print()
    print(analysis_brief(analysis))
    print()
    print(usage_report(records, summaries, analysis))
    print()
    print(f"Report: {paths.report}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    paths = _resolve_experiment(args.experiment)
    manifest = Manifest.load(paths.manifest)
    records = load_runs(paths)
    if not records:
        sys.exit("no runs found; run `skill-lab normalize` first")
    if args.run:
        wanted = {r.zfill(3) for r in args.run}
        for r in records:
            if r.run_id in wanted:
                print(run_detail(r))
                sp = summary_path(paths, r.run_id)
                if sp.exists():
                    print()
                    print(summary_detail(RunSummary.load(sp)))
                print()
        return 0
    print(experiment_header(manifest, records))
    print()
    print(runs_table(records))
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    paths = _resolve_experiment(args.experiment)
    records = load_runs(paths)
    if not records:
        sys.exit("no runs found; run `skill-lab normalize` first")
    if args.run:
        wanted = {r.zfill(3) for r in args.run}
        records = [r for r in records if r.run_id in wanted]
    model = ClaudeCliModel(model=args.model)
    pending = [r for r in records if args.force or not has_valid_summary(paths, r.run_id)]
    print(f"summarizing {len(pending)} run(s) with {args.model} via claude -p (concurrency {args.concurrency})", flush=True)
    summarize_experiment(
        paths, records, model, concurrency=args.concurrency, force=args.force,
        on_done=lambda s: print(f"  run {s.run_id}: {s.approach[:90]}", flush=True),
    )
    print(f"{len(load_summaries(paths))} summaries in {paths.runs_dir}")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    paths = _resolve_experiment(args.experiment)
    records = load_runs(paths)
    if not records:
        sys.exit("no runs found; run `skill-lab normalize` first")
    return _analyze(paths, records, args.model, args.concurrency, args.force)


def cmd_compare(args: argparse.Namespace) -> int:
    a = ExperimentBundle.load(_resolve_experiment(args.a))
    b = ExperimentBundle.load(_resolve_experiment(args.b))
    out_dir = args.output or (DEFAULT_ROOT.parent / "comparisons" / f"{a.manifest.id}--{b.manifest.id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Comparing {a.manifest.id} ({len(a.records)} runs) -> {b.manifest.id} ({len(b.records)} runs) with {args.model}...", flush=True)
    comparison = compare_experiments(a, b, ClaudeCliModel(model=args.model))
    comparison.save(out_dir / "comparison.json")
    (out_dir / "report.md").write_text(render_comparison(comparison))

    print()
    for w in comparison.compatibility_warnings:
        print(f"warning: {w}")
    print(frequency_table(comparison))
    print()
    print(f"Behavior consistency:\n  {a.manifest.id}: {comparison.consistency.get('a')}\n  {b.manifest.id}: {comparison.consistency.get('b')}")
    print()
    print(comparison.summary)
    for title, items in (("Improvements", comparison.improvements), ("New behavior in B", comparison.new_behaviors), ("Remaining issues", comparison.remaining_issues)):
        if items:
            print(f"\n{title}:")
            print("\n".join(f"  - {i}" for i in items))
    print(f"\nReport: {out_dir / 'report.md'}")
    return 0


def cmd_usage(args: argparse.Namespace) -> int:
    from skill_lab.models.analysis import Analysis

    paths = _resolve_experiment(args.experiment)
    records = load_runs(paths)
    analysis = Analysis.load(paths.analysis) if paths.analysis.exists() else None
    print(usage_report(records, load_summaries(paths), analysis))
    return 0


def cmd_normalize(args: argparse.Namespace) -> int:
    paths = _resolve_experiment(args.experiment)
    records = normalize_experiment(paths)
    print(f"normalized {len(records)} runs into {paths.runs_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="skill-lab", description="Run a skill many times and study how it behaves.")
    sub = ap.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run an experiment through Harbor")
    run.add_argument("--skill", type=Path, required=True, help="Local skill directory containing SKILL.md")
    run.add_argument("--repo", type=Path, required=True, help="Local repository fixture")
    run.add_argument("--prompt", help="Task prompt text")
    run.add_argument("--prompt-file", type=Path, help="File containing the task prompt")
    run.add_argument("--attempts", type=int, default=10,
                     help="Trials to run (default: 10). Raise to 20 when a frequency needs to be "
                          "trustworthy — e.g. a v1/v2 comparison, or hunting a behavior rarer than ~1 in 10")
    run.add_argument("--agent", default="claude-code")
    run.add_argument("--model", default="anthropic/claude-sonnet-5")
    run.add_argument("--concurrency", type=int, default=4)
    run.add_argument("--auth", choices=["subscription", "api"], default="subscription",
                     help="Bill rollouts to the Claude subscription (needs CLAUDE_CODE_OAUTH_TOKEN) or the API key")
    run.add_argument("--agent-timeout", type=float, default=900.0, help="Per-trial agent timeout in seconds")
    run.add_argument("--claude-code-version", default="latest", help="Claude Code version baked into the image")
    run.add_argument("--apt", nargs="+", metavar="PKG", help="Extra apt packages to install in the image (e.g. python3-docx)")
    run.add_argument("--interactive", action="store_true",
                     help="Multi-turn trial: a simulated user (Claude Code with a persona) answers the agent's questions")
    run.add_argument("--persona-file", type=Path,
                     help="Interactive mode: the simulated user's private goal and the answers it should give")
    run.add_argument("--user-model", default="anthropic/claude-sonnet-5", help="Model for the simulated user")
    run.add_argument("--name", help="Experiment id (default: timestamp)")
    run.add_argument("--output", type=Path, default=DEFAULT_ROOT, help="Experiments root directory")
    run.add_argument("--no-analyze", action="store_true", help="Stop after normalizing; skip summaries and analysis")
    run.add_argument("--analysis-model", default="sonnet", help="Claude model alias for summaries/analysis")
    run.add_argument("--analysis-concurrency", type=int, default=3)
    run.set_defaults(func=cmd_run)

    inspect = sub.add_parser("inspect", help="Print a table of runs for an experiment")
    inspect.add_argument("experiment", help="Experiment directory or id")
    inspect.add_argument("--run", nargs="+", help="Show full detail for these run ids")
    inspect.set_defaults(func=cmd_inspect)

    summarize = sub.add_parser("summarize", help="Write an LLM behavioral summary (summary.json) for each run")
    summarize.add_argument("experiment", help="Experiment directory or id")
    summarize.add_argument("--run", nargs="+", help="Only these run ids")
    summarize.add_argument("--model", default="sonnet", help="Claude model alias for the summarizer")
    summarize.add_argument("--concurrency", type=int, default=2)
    summarize.add_argument("--force", action="store_true", help="Re-summarize runs that already have a summary")
    summarize.set_defaults(func=cmd_summarize)

    analyze = sub.add_parser("analyze", help="Cross-run analysis -> analysis.json + report.md (summarizes first if needed)")
    analyze.add_argument("experiment", help="Experiment directory or id")
    analyze.add_argument("--model", default="sonnet", help="Claude model alias for summaries/analysis")
    analyze.add_argument("--concurrency", type=int, default=3, help="Parallel summarizer calls")
    analyze.add_argument("--force", action="store_true", help="Re-summarize every run before analyzing")
    analyze.set_defaults(func=cmd_analyze)

    compare = sub.add_parser("compare", help="Compare observed behavior between two experiments (e.g. skill v1 vs v2)")
    compare.add_argument("a", help="Baseline experiment directory or id")
    compare.add_argument("b", help="Revised experiment directory or id")
    compare.add_argument("--model", default="sonnet")
    compare.add_argument("--output", type=Path, help="Output directory (default: .skill-lab/comparisons/<a>--<b>)")
    compare.set_defaults(func=cmd_compare)

    usage = sub.add_parser("usage", help="Token and cost usage for an experiment: rollouts vs. analysis calls")
    usage.add_argument("experiment", help="Experiment directory or id")
    usage.set_defaults(func=cmd_usage)

    normalize = sub.add_parser("normalize", help="(Re)build runs/ from the experiment's Harbor job")
    normalize.add_argument("experiment", help="Experiment directory or id")
    normalize.set_defaults(func=cmd_normalize)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
