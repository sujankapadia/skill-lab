"""Compact structured description of what one run did (§12).

Descriptive, not evaluative: there is deliberately no pass/fail or score field.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class RunSummary:
    run_id: str
    approach: str
    steps: list[str]
    outcome: str
    notable_behaviors: list[str] = field(default_factory=list)
    possible_problems: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    # Provenance of the summary itself.
    model: str | None = None
    evidence_chars: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RunSummary":
        return cls(**data)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "RunSummary":
        return cls.from_dict(json.loads(path.read_text()))


# JSON Schema handed to the model for structured output. Descriptions carry
# the fact/inference/uncertainty framing so it survives prompt edits.
RUN_SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "approach": {
            "type": "string",
            "description": "One or two sentences: the overall strategy the agent used.",
        },
        "steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The run's main phases in order, each a short past-tense phrase "
                           "grounded in specific tool calls (e.g. 'read docs/architecture.md "
                           "and found it stale'). 3-10 items.",
        },
        "outcome": {
            "type": "string",
            "description": "What the workspace looked like at the end: files created/modified/deleted "
                           "and what they contain, per the diff. Observed facts only.",
        },
        "notable_behaviors": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observed behaviors a skill author would want to know about, good or bad, "
                           "including how the agent used (or ignored) the skill's instructions.",
        },
        "possible_problems": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Things that look wrong or risky. Prefix each with 'Observed:' when directly "
                           "visible in the evidence or 'Inferred:' when it is your judgment.",
        },
        "strengths": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Things the run did well relative to the task and the skill's intent. "
                           "Same Observed:/Inferred: prefixes.",
        },
        "uncertainties": {
            "type": "array",
            "items": {"type": "string"},
            "description": "What you cannot determine from the evidence (e.g. whether the written "
                           "content is accurate).",
        },
    },
    "required": ["approach", "steps", "outcome", "notable_behaviors",
                 "possible_problems", "strengths", "uncertainties"],
    "additionalProperties": False,
}
