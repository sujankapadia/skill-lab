"""Command-line entry point. Parses arguments and delegates to the service layer."""

import argparse
import sys

from inventory.api.server import serve
from inventory.config import store_from_env
from inventory.service import InventoryService
from inventory.worker.importer import import_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inventory")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add quantity of an item")
    add.add_argument("name")
    add.add_argument("quantity", type=int)

    remove = sub.add_parser("remove", help="Remove quantity of an item")
    remove.add_argument("name")
    remove.add_argument("quantity", type=int)

    sub.add_parser("list", help="List all items")

    serve_cmd = sub.add_parser("serve", help="Run the HTTP API")
    serve_cmd.add_argument("--port", type=int, default=8080)

    imp = sub.add_parser("import", help="Bulk import from a CSV of name,quantity rows")
    imp.add_argument("path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = InventoryService(store_from_env())

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
    elif args.command == "serve":
        serve(service, args.port)
    elif args.command == "import":
        report = import_csv(service, args.path)
        print(f"imported {report.imported} rows, skipped {report.skipped}")
    return 0
