import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from skill_lab.local_usage import Totals, collect, render


def _session(root: Path, project: str, name: str, events: list[dict]) -> Path:
    d = root / project
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in events) + "\n")
    return p


def _assistant(msg_id: str, model: str, when: datetime, **tokens) -> dict:
    usage = {"input_tokens": 0, "cache_creation_input_tokens": 0,
             "cache_read_input_tokens": 0, "output_tokens": 0, **tokens}
    return {"type": "assistant", "timestamp": when.isoformat().replace("+00:00", "Z"),
            "message": {"id": msg_id, "model": model, "role": "assistant", "usage": usage}}


def test_collect_dedupes_and_windows(tmp_path: Path):
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=48)
    _session(tmp_path, "proj-a", "s1", [
        _assistant("m1", "opus", now - timedelta(minutes=5), input_tokens=10, output_tokens=2),
        # same message id written twice (one line per content block) — counted once
        _assistant("m1", "opus", now - timedelta(minutes=5), input_tokens=10, output_tokens=2),
        _assistant("m2", "opus", now - timedelta(hours=1), cache_read_input_tokens=1000),
        _assistant("m3", "opus", old, input_tokens=99_999),          # outside the window
        {"type": "user", "timestamp": now.isoformat()},               # no usage
        "not json",
    ])
    _session(tmp_path, "proj-b", "s2", [
        _assistant("m4", "sonnet", now - timedelta(minutes=1), cache_creation_input_tokens=400, output_tokens=8),
    ])

    u = collect(hours=24, root=tmp_path)
    assert u.by_model["opus"].fresh == 10          # deduped, and the 48h-old row excluded
    assert u.by_model["opus"].cache_read == 1000
    assert u.by_model["sonnet"].output == 8
    assert u.total.fresh == 10 and u.total.cache_write == 400
    assert set(u.by_project) == {"proj-a", "proj-b"}

    out = render(u)
    assert "proj-a" in out and "proj-b" in out and "opus" in out


def test_weighting_ranks_output_above_cache_reads():
    reads = Totals(cache_read=1_000_000)
    out = Totals(output=100_000)
    assert out.weighted > reads.weighted          # 500k vs 100k


def test_collect_handles_missing_root(tmp_path: Path):
    u = collect(hours=24, root=tmp_path / "nope")
    assert u.total.weighted == 0
    assert "last 24h" in render(u)
