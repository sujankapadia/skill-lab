"""SQLite backed store. One table, one row per item."""

import sqlite3
from pathlib import Path


class SqliteStore:
    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS items (name TEXT PRIMARY KEY, quantity INTEGER NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def load(self) -> dict[str, int]:
        with self._connect() as conn:
            return dict(conn.execute("SELECT name, quantity FROM items"))

    def save(self, items: dict[str, int]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM items")
            conn.executemany("INSERT INTO items (name, quantity) VALUES (?, ?)", items.items())
