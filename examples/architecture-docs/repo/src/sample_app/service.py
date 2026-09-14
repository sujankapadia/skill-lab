"""Business rules for the inventory. Knows nothing about how data is persisted."""

from sample_app.storage.base import Store


class InventoryService:
    def __init__(self, store: Store) -> None:
        self._store = store

    def add(self, name: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        items = self._store.load()
        items[name] = items.get(name, 0) + quantity
        self._store.save(items)

    def remove(self, name: str, quantity: int) -> None:
        items = self._store.load()
        current = items.get(name, 0)
        if quantity > current:
            raise ValueError(f"cannot remove {quantity} {name}; only {current} in stock")
        remaining = current - quantity
        if remaining == 0:
            items.pop(name, None)
        else:
            items[name] = remaining
        self._store.save(items)

    def list_items(self) -> dict[str, int]:
        return dict(self._store.load())
