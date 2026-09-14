"""Minimal LLM abstraction for the summarizer/analyzer/comparator.

Every LLM-driven step in Skill Lab goes through ``AnalysisModel.generate_json``
so the backend (and who pays for it) is a single config switch.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Protocol


class AnalysisModel(Protocol):
    def generate_json(self, system_prompt: str, prompt: str, schema: dict) -> dict: ...


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
        # The CLI occasionally fails transiently (rate limit, API hiccup) with
        # a bare exit 1; retry with backoff before giving up.
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                result = self._call(system_prompt, prompt, schema)
                if looks_like_placeholder(result):
                    raise PlaceholderOutput(f"placeholder output: {json.dumps(result)[:200]}")
                return result
            except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                last = exc
                if attempt < self.retries:
                    time.sleep(5 * (attempt + 1))
        assert last is not None
        raise last

    def _call(self, system_prompt: str, prompt: str, schema: dict) -> dict:
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
        return output
