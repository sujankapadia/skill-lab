"""Runtime configuration from environment variables."""

import os

from inventory.storage.base import Store
from inventory.storage.json_store import JsonStore
from inventory.storage.sqlite_store import SqliteStore

DEFAULT_STORE_URL = "json:///inventory.json"


def store_from_env() -> Store:
    """Build the store named by INVENTORY_STORE (json:///path or sqlite:///path)."""
    return store_from_url(os.environ.get("INVENTORY_STORE", DEFAULT_STORE_URL))


def store_from_url(url: str) -> Store:
    scheme, _, path = url.partition("://")
    path = path.lstrip("/") or "inventory.json"
    if scheme == "json":
        return JsonStore(path)
    if scheme == "sqlite":
        return SqliteStore(path)
    raise ValueError(f"unknown store scheme: {scheme!r}")
