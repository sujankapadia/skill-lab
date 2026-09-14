"""Minimal JSON HTTP API over InventoryService. See docs/adr/0002-http-api.md.

GET  /items                 -> {"items": {name: quantity}}
POST /items/<name>/add      body {"quantity": n}
POST /items/<name>/remove   body {"quantity": n}
"""

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

from inventory.service import InventoryService

_ITEM_ROUTE = re.compile(r"^/items/([^/]+)/(add|remove)$")


def make_handler(service: InventoryService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:
            if self.path == "/items":
                self._send(200, {"items": service.list_items()})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:
            match = _ITEM_ROUTE.match(self.path)
            if not match:
                self._send(404, {"error": "not found"})
                return
            name, action = match.groups()
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                quantity = int(body["quantity"])
                getattr(service, action)(name, quantity)
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                self._send(400, {"error": str(exc)})
                return
            self._send(200, {"items": service.list_items()})

        def log_message(self, format: str, *args) -> None:  # quiet by default
            pass

    return Handler


def serve(service: InventoryService, port: int) -> None:
    HTTPServer(("127.0.0.1", port), make_handler(service)).serve_forever()
