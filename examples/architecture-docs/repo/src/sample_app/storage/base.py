"""Storage abstraction. Implementations persist a name -> quantity mapping."""

from typing import Protocol


class Store(Protocol):
    def load(self) -> dict[str, int]: ...

    def save(self, items: dict[str, int]) -> None: ...
