"""Storage abstraction. Implementations persist a name -> quantity mapping.

See docs/adr/0001-storage-protocol.md.
"""

from typing import Protocol


class Store(Protocol):
    def load(self) -> dict[str, int]: ...

    def save(self, items: dict[str, int]) -> None: ...
