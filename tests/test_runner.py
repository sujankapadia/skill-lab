from pathlib import Path

from skill_lab.harbor.runner import HarborRunner
from skill_lab.models.experiment import ExperimentConfig, ExperimentPaths


def _skill(tmp_path: Path) -> Path:
    d = tmp_path / "my-skill"
    d.mkdir()
    (d / "SKILL.md").write_text("---\nname: my-skill\n---\nDo it.\n")
    return d


def test_headless_task(tmp_path: Path, workspace: Path):
    cfg = ExperimentConfig(id="e", skill=_skill(tmp_path), repo=workspace, prompt="Go.", attempts=3, apt_packages=["jq"])
    r = HarborRunner(cfg, ExperimentPaths(tmp_path / "exp"))
    task = r.build_task()
    df = (task / "environment" / "Dockerfile").read_text()
    assert "procps jq" in df and ".claude/skills" not in df and "claude-code-acp" not in df
    assert (task / "instruction.md").read_text() == "Go.\n"
    assert not (task / "environment" / "repo" / ".git").exists()
    cmd = r.command("e")
    assert "--skill" in cmd and "--bridge" not in cmd


def test_interactive_task(tmp_path: Path, workspace: Path):
    cfg = ExperimentConfig(id="e", skill=_skill(tmp_path), repo=workspace, prompt="Go.", attempts=3,
                           interactive=True, persona="You want X.\n- answer: yes\n", user_model="anthropic/claude-haiku-4-5")
    r = HarborRunner(cfg, ExperimentPaths(tmp_path / "exp"))
    task = r.build_task()
    df = (task / "environment" / "Dockerfile").read_text()
    assert "COPY skill/ /app/.claude/skills/my-skill/" in df
    assert "COPY claude-code-acp-wrapper /usr/local/sbin/claude-code-acp" in df
    assert (task / "environment" / "skill" / "SKILL.md").exists()
    wrapper = (task / "environment" / "claude-code-acp-wrapper").read_text()
    assert "/proc/1/environ" in wrapper and wrapper.startswith("#!/usr/bin/env node")
    assert (task / "instruction.md").read_text().startswith("You want X.")
    cmd = r.command("e")
    assert "--skill" not in cmd
    assert cmd[cmd.index("--bridge") + 1] == "acp" and "--user-agent" in cmd
    assert cmd[cmd.index("--user-model") + 1] == "anthropic/claude-haiku-4-5"


def test_token_inject_and_scrub(tmp_path: Path, workspace: Path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat-test")
    cfg = ExperimentConfig(id="e", skill=_skill(tmp_path), repo=workspace, prompt="Go.", attempts=1, interactive=True, persona="p")
    r = HarborRunner(cfg, ExperimentPaths(tmp_path / "exp"))
    task = r.build_task()
    toml = task / "task.toml"
    before = toml.read_text()
    r._inject_token()
    assert 'CLAUDE_CODE_OAUTH_TOKEN = "sk-ant-oat-test"' in toml.read_text()
    r._scrub_token()
    assert toml.read_text() == before and "sk-ant" not in toml.read_text()
