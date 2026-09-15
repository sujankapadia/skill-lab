"""Cross-run analysis output (§13, §14): analysis.json.

Every finding carries the run ids it rests on, so a skill author can trace
any claim back to actual runs. Frequencies are observed behavioral
frequencies, not quality scores.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from skill_lab.analysis.model import ModelUsage


@dataclass
class Finding:
    """A pattern, problem or outlier, with the runs that exhibit it."""

    title: str
    description: str
    run_ids: list[str] = field(default_factory=list)
    basis: str = "observed"  # "observed" | "inferred"


@dataclass
class Cluster:
    name: str
    description: str
    run_ids: list[str] = field(default_factory=list)


@dataclass
class StrongRun:
    run_id: str
    reasons: list[str] = field(default_factory=list)


@dataclass
class SuggestedChange:
    change: str            # concrete text or instruction to add/modify in SKILL.md
    motivation: str        # the observed behavior that motivates it
    run_ids: list[str] = field(default_factory=list)


@dataclass
class Analysis:
    experiment_id: str
    run_count: int
    completed_count: int
    overview: str
    clusters: list[Cluster] = field(default_factory=list)
    recurring_patterns: list[Finding] = field(default_factory=list)
    recurring_problems: list[Finding] = field(default_factory=list)
    outliers: list[Finding] = field(default_factory=list)
    strong_runs: list[StrongRun] = field(default_factory=list)
    skill_observations: list[str] = field(default_factory=list)
    suggested_changes: list[SuggestedChange] = field(default_factory=list)
    model: str | None = None
    input_chars: int | None = None
    usage: ModelUsage | None = None          # this analysis call
    summaries_usage: ModelUsage | None = None  # the per-run summaries it read

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Analysis":
        data = dict(data)
        data["usage"] = ModelUsage.from_dict(data.get("usage"))
        data["summaries_usage"] = ModelUsage.from_dict(data.get("summaries_usage"))
        data["clusters"] = [Cluster(**c) for c in data.get("clusters", [])]
        for key in ("recurring_patterns", "recurring_problems", "outliers"):
            data[key] = [Finding(**f) for f in data.get(key, [])]
        data["strong_runs"] = [StrongRun(**s) for s in data.get("strong_runs", [])]
        data["suggested_changes"] = [SuggestedChange(**s) for s in data.get("suggested_changes", [])]
        return cls(**data)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "Analysis":
        return cls.from_dict(json.loads(path.read_text()))


_RUN_IDS = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Zero-padded run ids (e.g. \"003\") this rests on. Must be run ids from the input.",
}

_FINDING = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short label."},
        "description": {"type": "string", "description": "What was observed, concretely, with counts (e.g. '8 of 20 runs ...')."},
        "run_ids": _RUN_IDS,
        "basis": {"type": "string", "enum": ["observed", "inferred"],
                  "description": "'observed' if directly visible in the run evidence; 'inferred' if a judgment."},
    },
    "required": ["title", "description", "run_ids", "basis"],
    "additionalProperties": False,
}

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "overview": {
            "type": "string",
            "description": "Three to six sentences a skill author would read first: what the runs "
                           "generally did, how consistent they were, and the headline finding.",
        },
        "clusters": {
            "type": "array",
            "description": "Distinct execution strategies. Every run belongs to exactly one cluster. "
                           "Merge clusters that differ only in trivial ways; split when the difference "
                           "would matter to the skill author.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Short kebab-case name, e.g. 'inspect-then-update'."},
                    "description": {"type": "string", "description": "The strategy, in one or two sentences."},
                    "run_ids": _RUN_IDS,
                },
                "required": ["name", "description", "run_ids"],
                "additionalProperties": False,
            },
        },
        "recurring_patterns": {
            "type": "array", "items": _FINDING,
            "description": "Behaviors seen across many runs, whether or not they are problems.",
        },
        "recurring_problems": {
            "type": "array", "items": _FINDING,
            "description": "Apparent errors, deviations from the task or skill intent, or risky behavior "
                           "seen in more than one run.",
        },
        "outliers": {
            "type": "array", "items": _FINDING,
            "description": "Runs that differ markedly from the rest (in either direction).",
        },
        "strong_runs": {
            "type": "array",
            "description": "Runs that appear especially focused, complete, conservative or well-aligned "
                           "with the task and skill. Explain why; do not claim ground truth.",
            "items": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["run_id", "reasons"],
                "additionalProperties": False,
            },
        },
        "skill_observations": {
            "type": "array", "items": {"type": "string"},
            "description": "Where SKILL.md appears ambiguous, silent, or misread, as evidenced by the "
                           "variation or problems above. Quote or reference the relevant instruction.",
        },
        "suggested_changes": {
            "type": "array",
            "description": "Concrete edits to SKILL.md, each tied to the observed behavior motivating it.",
            "items": {
                "type": "object",
                "properties": {
                    "change": {"type": "string", "description": "The instruction to add or rewrite, as text the author could paste."},
                    "motivation": {"type": "string", "description": "The recurring behavior or problem this addresses, with counts."},
                    "run_ids": _RUN_IDS,
                },
                "required": ["change", "motivation", "run_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["overview", "clusters", "recurring_patterns", "recurring_problems",
                 "outliers", "strong_runs", "skill_observations", "suggested_changes"],
    "additionalProperties": False,
}
