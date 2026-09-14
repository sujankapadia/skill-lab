"""Bulk import: apply a CSV of `name,quantity` rows to the inventory."""

import csv
from dataclasses import dataclass
from pathlib import Path

from inventory.service import InventoryService


@dataclass
class ImportReport:
    imported: int = 0
    skipped: int = 0


def import_csv(service: InventoryService, path: str | Path) -> ImportReport:
    report = ImportReport()
    with open(path, newline="") as fh:
        for row in csv.reader(fh):
            if not row or row[0].startswith("#"):
                report.skipped += 1
                continue
            name, quantity = row[0].strip(), int(row[1])
            # TODO: negative quantities should be treated as removals; today they
            # raise inside service.add() and abort the whole import.
            service.add(name, quantity)
            report.imported += 1
    return report
