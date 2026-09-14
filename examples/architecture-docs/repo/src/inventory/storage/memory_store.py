"""In-memory store, used by tests."""


class MemoryStore:
    def __init__(self) -> None:
        self._items: dict[str, int] = {}

    def load(self) -> dict[str, int]:
        return dict(self._items)

    def save(self, items: dict[str, int]) -> None:
        self._items = dict(items)
