"""JSON-file backed store (the default)."""

import json
from pathlib import Path


class JsonStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> dict[str, int]:
        if not self._path.exists():
            return {}
        return json.loads(self._path.read_text())

    def save(self, items: dict[str, int]) -> None:
        self._path.write_text(json.dumps(items, indent=2, sort_keys=True))
