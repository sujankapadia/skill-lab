"""Experiment lifecycle: create, execute via Harbor, normalize into runs/."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from skill_lab.harbor.parser import HarborJobParser
from skill_lab.harbor.runner import HarborRunner
from skill_lab.models.experiment import ExperimentConfig, ExperimentPaths, Manifest, build_manifest
from skill_lab.models.run_record import RunRecord

DEFAULT_ROOT = Path(".skill-lab/experiments")


def run_experiment(config: ExperimentConfig, root: Path) -> ExperimentPaths:
    """Write the manifest, run Harbor, normalize. Returns the experiment paths."""
    paths = ExperimentPaths(root / config.id)
    if paths.manifest.exists():
        raise FileExistsError(f"experiment already exists: {paths.root}")
    paths.root.mkdir(parents=True)

    job_name = config.id
    manifest = build_manifest(config, job_name)
    manifest.save(paths.manifest)
    # Snapshot the skill so later analysis reads what actually ran, not
    # whatever the author has edited since.
    shutil.copytree(config.skill, paths.skill_dir)

    runner = HarborRunner(config, paths)
    runner.build_task()
    job_dir = runner.run(job_name)

    normalize_experiment(paths, job_dir)
    return paths


def normalize_experiment(paths: ExperimentPaths, job_dir: Path | None = None) -> list[RunRecord]:
    """Turn every Harbor trial into runs/NNN/{run.json, diff.patch, diff-stat.json}.

    Idempotent: re-running overwrites the run files. Large data (trajectory,
    workspace) is referenced by path, not copied.
    """
    manifest = Manifest.load(paths.manifest)
    if job_dir is None:
        job_dir = paths.harbor_job_dir(manifest.harbor["job_name"])
    parser = HarborJobParser(job_dir)

    records = []
    for index, trial in enumerate(parser.trials(), 1):
        run_id = f"{index:03d}"
        run_dir = paths.run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)

        record, changes = parser.normalize(trial, manifest.id, run_id, run_dir)
        if changes is not None:
            patch_path = run_dir / "diff.patch"
            patch_path.write_text(changes.patch)
            record.diff_patch_path = str(patch_path)
            (run_dir / "diff-stat.json").write_text(json.dumps({
                "files_created": changes.files_created,
                "files_modified": changes.files_modified,
                "files_deleted": changes.files_deleted,
                **changes.stats.__dict__,
            }, indent=2))
        record.save(run_dir / "run.json")
        records.append(record)

    # Cross-check the digest Harbor computed against ours.
    trials = parser.trials()
    if trials and trials[0].skill_digest and trials[0].skill_digest != manifest.skill["digest"]:
        print(f"warning: Harbor skill digest {trials[0].skill_digest} != manifest {manifest.skill['digest']}")
    return records


def load_runs(paths: ExperimentPaths) -> list[RunRecord]:
    return [RunRecord.load(p) for p in sorted(paths.runs_dir.glob("*/run.json"))]
