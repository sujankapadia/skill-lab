from inventory.storage.json_store import JsonStore
from inventory.storage.sqlite_store import SqliteStore


def test_json_store_round_trip(tmp_path):
    store = JsonStore(tmp_path / "inv.json")
    assert store.load() == {}
    store.save({"a": 1})
    assert store.load() == {"a": 1}


def test_sqlite_store_round_trip(tmp_path):
    store = SqliteStore(tmp_path / "inv.db")
    assert store.load() == {}
    store.save({"a": 1, "b": 2})
    assert store.load() == {"a": 1, "b": 2}
