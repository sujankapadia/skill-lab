# Inventory Service

A small inventory service with a command-line interface, an HTTP API, and a
CSV import worker. Stock levels are kept in a pluggable store (JSON file or
SQLite).

## Usage

```bash
python -m inventory add widget 5          # CLI
python -m inventory list
python -m inventory serve --port 8080     # HTTP API
python -m inventory import stock.csv      # bulk import
```

Set `INVENTORY_STORE=sqlite:///inventory.db` to use SQLite instead of the
default `inventory.json`.

## Architecture

The service has two packages: `cli`, which parses commands, and `store`, which
persists items to `inventory.json`. See `docs/architecture.md` for details.

## Development

```bash
python -m pytest
```
