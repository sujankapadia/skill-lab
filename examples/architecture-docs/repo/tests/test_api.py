import json
import threading
from http.client import HTTPConnection
from http.server import HTTPServer

import pytest

from inventory.api.server import make_handler
from inventory.service import InventoryService
from inventory.storage.memory_store import MemoryStore


@pytest.fixture
def server():
    service = InventoryService(MemoryStore())
    httpd = HTTPServer(("127.0.0.1", 0), make_handler(service))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()


def _request(port, method, path, body=None):
    conn = HTTPConnection("127.0.0.1", port)
    conn.request(method, path, body=json.dumps(body) if body else None,
                 headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    return resp.status, json.loads(resp.read())


def test_add_then_list(server):
    assert _request(server, "POST", "/items/widget/add", {"quantity": 3}) == (200, {"items": {"widget": 3}})
    assert _request(server, "GET", "/items") == (200, {"items": {"widget": 3}})


def test_remove_too_many_is_400(server):
    status, body = _request(server, "POST", "/items/widget/remove", {"quantity": 1})
    assert status == 400 and "only 0 in stock" in body["error"]
