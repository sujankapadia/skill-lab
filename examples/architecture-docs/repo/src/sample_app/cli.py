"""Command-line entry point. Parses arguments and delegates to the service layer."""

import argparse
import sys

from sample_app.service import InventoryService
from sample_app.storage.json_store import JsonStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sample_app")
    parser.add_argument("--store", default="inventory.json", help="Path to the JSON store")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add quantity of an item")
    add.add_argument("name")
    add.add_argument("quantity", type=int)

    remove = sub.add_parser("remove", help="Remove quantity of an item")
    remove.add_argument("name")
    remove.add_argument("quantity", type=int)

    sub.add_parser("list", help="List all items")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = InventoryService(JsonStore(args.store))

    if args.command == "add":
        service.add(args.name, args.quantity)
    elif args.command == "remove":
        try:
            service.remove(args.name, args.quantity)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    elif args.command == "list":
        for name, qty in sorted(service.list_items().items()):
            print(f"{name}\t{qty}")
    return 0
