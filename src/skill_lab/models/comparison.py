"""Comparison of two experiments that differ (ideally) only in skill version (§17)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from skill_lab.analysis.model import ModelUsage


@dataclass
class BehaviorFrequency:
    """One observable behavior with the runs exhibiting it in each experiment.

    Counts are derived from the run-id lists, never reported by the model.
    """

    behavior: str
    a_run_ids: list[str] = field(default_factory=list)
    b_run_ids: list[str] = field(default_factory=list)


@dataclass
class Comparison:
    a_id: str
    b_id: str
    a_run_count: int
    b_run_count: int
    a_skill_digest: str
    b_skill_digest: str
    skill_diff: str
    compatibility_warnings: list[str]
    summary: str
    behaviors: list[BehaviorFrequency] = field(default_factory=list)
    consistency: dict = field(default_factory=dict)  # {"a": "...", "b": "..."} with rationale
    improvements: list[str] = field(default_factory=list)
    new_behaviors: list[str] = field(default_factory=list)
    remaining_issues: list[str] = field(default_factory=list)
    model: str | None = None
    input_chars: int | None = None
    usage: ModelUsage | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Comparison":
        data = dict(data)
        data["usage"] = ModelUsage.from_dict(data.get("usage"))
        data["behaviors"] = [BehaviorFrequency(**b) for b in data.get("behaviors", [])]
        return cls(**data)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "Comparison":
        return cls.from_dict(json.loads(path.read_text()))


_RUN_IDS = {"type": "array", "items": {"type": "string"}}

COMPARISON_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "Three to six sentences: what changed materially between A and B, and whether "
                           "the skill edit appears to have had its intended effect.",
        },
        "behaviors": {
            "type": "array",
            "description": "Observable behaviors worth tracking across versions: the ones the skill edit "
                           "targeted, the ones that recurred as problems, and any that newly appeared. "
                           "6-12 items. For each, list the runs in A and in B that exhibit it. An empty "
                           "list means no run did. Do not report counts; they are computed from the lists.",
            "items": {
                "type": "object",
                "properties": {
                    "behavior": {"type": "string", "description": "Short, concrete, positively phrased (e.g. 'Updated existing docs/architecture.md in place')."},
                    "a_run_ids": _RUN_IDS,
                    "b_run_ids": _RUN_IDS,
                },
                "required": ["behavior", "a_run_ids", "b_run_ids"],
                "additionalProperties": False,
            },
        },
        "consistency": {
            "type": "object",
            "description": "How uniform the runs' behavior was within each experiment.",
            "properties": {
                "a": {"type": "string", "description": "low | medium | high, followed by a one-sentence reason."},
                "b": {"type": "string", "description": "low | medium | high, followed by a one-sentence reason."},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        "improvements": {
            "type": "array", "items": {"type": "string"},
            "description": "Apparent problems from A that are reduced or gone in B, each citing the behavior counts.",
        },
        "new_behaviors": {
            "type": "array", "items": {"type": "string"},
            "description": "Behaviors present in B but not A, including regressions or side effects of the edit.",
        },
        "remaining_issues": {
            "type": "array", "items": {"type": "string"},
            "description": "What is still inconsistent or problematic in B, with run ids.",
        },
    },
    "required": ["summary", "behaviors", "consistency", "improvements", "new_behaviors", "remaining_issues"],
    "additionalProperties": False,
}
