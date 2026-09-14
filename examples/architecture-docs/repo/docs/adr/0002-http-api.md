# ADR 0002: HTTP API on the standard library

**Status:** accepted

## Context

Other tools need to read and adjust stock without shelling out to the CLI.

## Decision

Expose a minimal JSON API (`inventory/api/server.py`) using
`http.server` from the standard library — no web framework dependency.
Endpoints: `GET /items`, `POST /items/<name>/add`, `POST /items/<name>/remove`.
The API constructs the same `InventoryService` the CLI uses.

## Consequences

No dependencies, but also no auth, no concurrency control, and one request at a
time. Acceptable for an internal tool.
