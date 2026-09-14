from pathlib import Path

from conftest import git
from skill_lab.workspace.git_diff import workspace_changes


def test_clean_workspace(workspace: Path):
    c = workspace_changes(workspace)
    assert (c.files_created, c.files_modified, c.files_deleted) == ([], [], [])
    assert c.stats.files_changed == 0
    assert c.patch == ""


def test_created_modified_deleted(workspace: Path):
    (workspace / "docs" / "architecture.md").write_text("old\nstale\nnew line\n")
    (workspace / "docs" / "new.md").write_text("a\nb\n")
    (workspace / "src" / "main.py").unlink()

    c = workspace_changes(workspace)
    assert c.files_created == ["docs/new.md"]
    assert c.files_modified == ["docs/architecture.md"]
    assert c.files_deleted == ["src/main.py"]
    assert c.stats.files_changed == 3
    assert c.stats.insertions == 3  # 1 in architecture.md + 2 in new.md
    assert c.stats.deletions == 1
    assert "+++ b/docs/new.md" in c.patch
    assert "--- a/src/main.py" in c.patch


def test_does_not_touch_real_index(workspace: Path):
    (workspace / "docs" / "new.md").write_text("x\n")
    workspace_changes(workspace)
    # Untracked file must still be untracked in the real index.
    assert git(workspace, "status", "--porcelain").strip() == "?? docs/new.md"
