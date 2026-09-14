import pytest

from inventory.service import InventoryService
from inventory.storage.memory_store import MemoryStore


def make_service() -> InventoryService:
    return InventoryService(MemoryStore())


def test_add_and_list():
    svc = make_service()
    svc.add("widget", 5)
    svc.add("widget", 2)
    assert svc.list_items() == {"widget": 7}


def test_remove_to_zero_deletes_item():
    svc = make_service()
    svc.add("widget", 3)
    svc.remove("widget", 3)
    assert svc.list_items() == {}


def test_remove_more_than_stock_fails():
    svc = make_service()
    svc.add("widget", 1)
    with pytest.raises(ValueError):
        svc.remove("widget", 2)
