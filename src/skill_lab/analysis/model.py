"""Minimal LLM abstraction for the summarizer/analyzer/comparator.

Every LLM-driven step in Skill Lab goes through ``AnalysisModel.generate_json``
so the backend (and who pays for it) is a single config switch.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Protocol


class AnalysisModel(Protocol):
    def generate_json(self, system_prompt: str, prompt: str, schema: dict) -> dict: ...


class ClaudeCliModel:
    """Backend that shells out to ``claude -p`` so calls bill the user's Claude
    subscription rather than API usage.

    Runs headless with all tools, settings, hooks and MCP servers disabled and an
    explicit system prompt, which drops the per-call context from ~47k tokens
    (this user's global CLAUDE.md, skills, MCP) to ~1k. Structured output comes
    back under ``structured_output`` in the JSON envelope.
    """

    def __init__(self, model: str = "sonnet", timeout_s: float = 300.0) -> None:
        self.model = model
        self.timeout_s = timeout_s

    def generate_json(self, system_prompt: str, prompt: str, schema: dict) -> dict:
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
            raise RuntimeError(f"claude -p failed ({proc.returncode}): {proc.stderr.strip()[:2000]}")
        envelope = json.loads(proc.stdout)
        if envelope.get("is_error"):
            raise RuntimeError(f"claude -p returned an error: {envelope.get('result')}")
        output = envelope.get("structured_output")
        if output is None:
            raise RuntimeError("claude -p returned no structured_output; envelope subtype="
                               f"{envelope.get('subtype')}")
        return output
