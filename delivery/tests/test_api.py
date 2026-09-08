import json
import os
import threading

import pytest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from delivery.app import app


class PaymentHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else b"{}"
        self.server.last_payload = body.decode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"verified"}')

    def log_message(self, format, *args):
        return


@pytest.fixture
def payment_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), PaymentHandler)
    server.last_payload = ""
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    old_url = os.environ.get("PAYMENTS_SERVICE_URL")
    os.environ["PAYMENTS_SERVICE_URL"] = f"http://127.0.0.1:{server.server_port}/payments/verify"

    yield server

    server.shutdown()
    server.server_close()
    if old_url is None:
        os.environ.pop("PAYMENTS_SERVICE_URL", None)
    else:
        os.environ["PAYMENTS_SERVICE_URL"] = old_url


@pytest.fixture
def client(payment_server):
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client


def test_create_delivery_succeeds(client):
    payload = {
        "order_id": "ORD-1001",
        "student_id": "STU-2001",
        "pickup_location": "Library Gate",
        "dropoff_location": "Hostel C-block",
    }
    response = client.post(
        "/deliveries",
        json=payload,
        headers={"Idempotency-Key": "create-1"},
    )

    assert response.status_code == 201
    assert "Location" in response.headers
    assert response.headers["Location"].startswith("/deliveries/")
    body = response.get_json()
    assert body["order_id"] == "ORD-1001"
    assert "customer_id" not in body


def test_idempotent_repeat_returns_original(client):
    payload = {
        "order_id": "ORD-1002",
        "student_id": "STU-2002",
        "pickup_location": "Canteen",
        "dropoff_location": "Library",
    }
    headers = {"Idempotency-Key": "repeat-1"}

    first = client.post("/deliveries", json=payload, headers=headers)
    second = client.post("/deliveries", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.get_json() == first.get_json()


def test_malformed_body_rejected(client):
    response = client.post(
        "/deliveries",
        json={
            "order_id": "ORD-1003",
            "student_id": "STU-2003",
            "pickup_location": "A",
        },
        headers={"Idempotency-Key": "bad-body"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["status"] == 400
    assert body["title"] == "Invalid request"


def test_unknown_delivery_returns_404(client):
    response = client.get("/deliveries/unknown-id")

    assert response.status_code == 404
    body = response.get_json()
    assert body["status"] == 404
    assert body["title"] == "Not found"
