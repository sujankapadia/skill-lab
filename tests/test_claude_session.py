import json
from pathlib import Path

from skill_lab.harbor.claude_session import convert_session, find_session_files
from skill_lab.harbor.trajectory import parse_trajectory


def _write_session(tmp_path: Path) -> Path:
    d = tmp_path / "agent" / "sessions" / "projects" / "-app"
    d.mkdir(parents=True)
    lines = [
        {"type": "queue-operation", "timestamp": "2026-09-15T00:00:00.000Z"},
        {"type": "user", "timestamp": "2026-09-15T00:00:01.000Z", "message": {"role": "user", "content": "Draft an SOW for Acme."}},
        # one API message written as two lines (text block, then tool_use block)
        {"type": "assistant", "timestamp": "2026-09-15T00:00:02.000Z", "version": "2.1.271",
         "message": {"id": "m1", "model": "claude-sonnet-5", "role": "assistant",
                     "content": [{"type": "text", "text": "Using the skill."}],
                     "usage": {"input_tokens": 2, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 50, "output_tokens": 10}}},
        {"type": "assistant", "timestamp": "2026-09-15T00:00:02.100Z", "version": "2.1.271",
         "message": {"id": "m1", "model": "claude-sonnet-5", "role": "assistant",
                     "content": [{"type": "tool_use", "id": "t1", "name": "mcp__acp__Bash", "input": {"command": "ls"}}],
                     "usage": {"input_tokens": 2, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 50, "output_tokens": 10}}},
        {"type": "user", "timestamp": "2026-09-15T00:00:03.000Z", "toolUseResult": {"stdout": "README.md", "stderr": ""},
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "README.md\n\n[stdout]\nREADME.md"}]}},
        {"type": "assistant", "timestamp": "2026-09-15T00:00:04.000Z", "version": "2.1.271",
         "message": {"id": "m2", "model": "claude-sonnet-5", "role": "assistant",
                     "content": [{"type": "text", "text": "Which engagement type?"}],
                     "usage": {"input_tokens": 1, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 150, "output_tokens": 5}}},
    ]
    (d / "s1.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    (d / "memory").mkdir()
    (d / "memory" / "x.jsonl").write_text("{}\n")
    return tmp_path / "agent"


def test_convert_session_merges_blocks_and_attaches_results(tmp_path: Path):
    files = find_session_files(_write_session(tmp_path))
    assert [f.name for f in files] == ["s1.jsonl"]  # memory/ excluded
    t = convert_session(files)
    assert t["agent"] == {"name": "claude-code", "version": "2.1.271", "model_name": "claude-sonnet-5"}
    steps = t["steps"]
    assert [s["source"] for s in steps] == ["user", "agent", "agent"]
    a = steps[1]
    assert a["message"] == "Using the skill."
    assert a["tool_calls"] == [{"tool_call_id": "t1", "function_name": "Bash", "arguments": {"command": "ls"}}]
    assert a["observation"]["results"][0]["extra"]["tool_result_metadata"]["tool_use_result"]["stdout"] == "README.md"
    # usage counted once per message id, not once per line
    assert a["metrics"] == {"prompt_tokens": 152, "completion_tokens": 10, "cached_tokens": 50}
    assert t["final_metrics"]["total_prompt_tokens"] == 152 + 151
    assert steps[2]["observation"] is None


def test_parse_converted_trajectory_flags_awaiting_input(tmp_path: Path):
    files = find_session_files(_write_session(tmp_path))
    out = tmp_path / "trajectory.json"
    out.write_text(json.dumps(convert_session(files)))
    facts = parse_trajectory(out)
    assert [tc.name for tc in facts.tool_calls] == ["Bash"]
    assert facts.commands == ["ls"]
    assert facts.final_response == "Which engagement type?"
    assert facts.awaiting_input is True
    assert facts.user_turns == 0
