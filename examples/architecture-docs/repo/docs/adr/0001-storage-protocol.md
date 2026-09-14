# ADR 0001: Storage behind a protocol

**Status:** accepted

## Context

The first version wrote `inventory.json` directly from the command handlers,
which made it impossible to test business rules without touching the disk and
blocked adding other backends.

## Decision

All persistence goes through the `Store` protocol (`inventory/storage/base.py`)
with `load() -> dict[str, int]` and `save(items)`. `InventoryService` depends
only on that protocol. Backends: `JsonStore` (default), `SqliteStore`, and
`MemoryStore` (tests).

## Consequences

Business rules live in one place (`service.py`) and are tested against
`MemoryStore`. Adding a backend means implementing two methods.
