from inventory.service import InventoryService
from inventory.storage.memory_store import MemoryStore
from inventory.worker.importer import import_csv


def test_import_applies_rows_and_skips_comments(tmp_path):
    csv_path = tmp_path / "stock.csv"
    csv_path.write_text("# name,quantity\nwidget,5\ngadget,2\nwidget,1\n")
    svc = InventoryService(MemoryStore())
    report = import_csv(svc, csv_path)
    assert (report.imported, report.skipped) == (3, 1)
    assert svc.list_items() == {"widget": 6, "gadget": 2}
