"""Minimal LLM abstraction for the summarizer/analyzer/comparator.

Every LLM-driven step in Skill Lab goes through ``AnalysisModel.generate_json``
so the backend (and who pays for it) is a single config switch.

Analysis calls are not free: a 20-run experiment makes ~21 of them, which on a
Claude subscription draws from the same budget as the rollouts. Backends that
can report usage implement ``generate`` and return it alongside the result;
``call_model`` adapts either shape so callers can record it.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass
class ModelUsage:
    """What one analysis call consumed."""

    input_tokens: int | None = None
    cache_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "ModelUsage | None":
        return cls(**data) if data else None

    def __add__(self, other: "ModelUsage") -> "ModelUsage":
        def add(a, b):
            return None if a is None and b is None else (a or 0) + (b or 0)

        return ModelUsage(
            add(self.input_tokens, other.input_tokens),
            add(self.cache_tokens, other.cache_tokens),
            add(self.output_tokens, other.output_tokens),
            add(self.cost_usd, other.cost_usd),
        )


class AnalysisModel(Protocol):
    def generate_json(self, system_prompt: str, prompt: str, schema: dict) -> dict: ...


def call_model(
    model: AnalysisModel, system_prompt: str, prompt: str, schema: dict
) -> tuple[dict, ModelUsage | None]:
    """Call *model*, returning its result and usage when the backend reports it."""
    generate = getattr(model, "generate", None)
    if callable(generate):
        return generate(system_prompt=system_prompt, prompt=prompt, schema=schema)
    return model.generate_json(system_prompt=system_prompt, prompt=prompt, schema=schema), None


class PlaceholderOutput(RuntimeError):
    """The model filled the schema with dummy values instead of content."""


_PLACEHOLDERS = {"test", "string", "a", "b", "c", "x", "y", "z", "foo", "bar", "todo", "n/a", "...", ""}


def looks_like_placeholder(value: dict, min_chars: int = 12) -> bool:
    """True if a structured-output object is dummy filler rather than content.

    Seen in the wild: ``{"approach": "test", "steps": ["a", "b", "c"]}``. Only
    top-level string fields and top-level lists of strings are checked — nested
    objects legitimately hold short strings (run ids, enum values, names).
    """
    strings: list[str] = []
    for v in value.values():
        if isinstance(v, str):
            strings.append(v.strip())
        elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            strings.extend(x.strip() for x in v)
    if not strings:
        return False
    bad = sum(1 for x in strings if x.lower() in _PLACEHOLDERS or len(x) < min_chars)
    return bad * 2 > len(strings)


class ClaudeCliModel:
    """Backend that shells out to ``claude -p`` so calls bill the user's Claude
    subscription rather than API usage.

    Runs headless with all tools, settings, hooks and MCP servers disabled and an
    explicit system prompt, which drops the per-call context from ~47k tokens
    (this user's global CLAUDE.md, skills, MCP) to ~1k. Structured output comes
    back under ``structured_output`` in the JSON envelope.
    """

    def __init__(self, model: str = "sonnet", timeout_s: float = 300.0, retries: int = 2) -> None:
        self.model = model
        self.timeout_s = timeout_s
        self.retries = retries

    def generate_json(self, system_prompt: str, prompt: str, schema: dict) -> dict:
        return self.generate(system_prompt, prompt, schema)[0]

    def generate(
        self, system_prompt: str, prompt: str, schema: dict
    ) -> tuple[dict, ModelUsage | None]:
        # The CLI occasionally fails transiently (rate limit, API hiccup) with
        # a bare exit 1; retry with backoff before giving up. Usage from a
        # failed attempt is not recorded, so recorded totals are a floor.
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                result, usage = self._call(system_prompt, prompt, schema)
                if looks_like_placeholder(result):
                    raise PlaceholderOutput(f"placeholder output: {json.dumps(result)[:200]}")
                return result, usage
            except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                last = exc
                if attempt < self.retries:
                    time.sleep(5 * (attempt + 1))
        assert last is not None
        raise last

    def _call(self, system_prompt: str, prompt: str, schema: dict) -> tuple[dict, ModelUsage | None]:
        # Without the API key the CLI falls back to the logged-in subscription.
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        cmd = [
            "claude", "-p", prompt,
            "--model", self.model,
            "--system-prompt", system_prompt,
            "--output-format", "json",
            "--json-schema", json.dumps(schema),
            "--tools", "",
            "--setting-sources", "",
            "--strict-mcp-config",
            "--disable-slash-commands",
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, env=env, timeout=self.timeout_s, cwd="/",  # no project dir, so nothing else gets pulled into context
        )
        if proc.returncode != 0:
            detail = (proc.stderr.strip() or proc.stdout.strip())[-2000:]
            raise RuntimeError(f"claude -p failed ({proc.returncode}): {detail or '(no output)'}")
        envelope = json.loads(proc.stdout)
        if envelope.get("is_error"):
            raise RuntimeError(f"claude -p returned an error: {envelope.get('result')}")
        output = envelope.get("structured_output")
        if output is None:
            raise RuntimeError("claude -p returned no structured_output; envelope subtype="
                               f"{envelope.get('subtype')}")
        return output, _usage_from_envelope(envelope)


def _usage_from_envelope(envelope: dict) -> ModelUsage | None:
    """Pull token counts and cost out of the `claude -p --output-format json`
    envelope. `input_tokens` counts everything sent (fresh + cache creation +
    cache reads), matching how RunRecord reports rollout usage."""
    usage = envelope.get("usage")
    if not isinstance(usage, dict):
        return None
    cache_read = usage.get("cache_read_input_tokens") or 0
    total_input = (
        (usage.get("input_tokens") or 0)
        + (usage.get("cache_creation_input_tokens") or 0)
        + cache_read
    )
    return ModelUsage(
        input_tokens=total_input,
        cache_tokens=cache_read,
        output_tokens=usage.get("output_tokens") or 0,
        cost_usd=envelope.get("total_cost_usd"),
    )
