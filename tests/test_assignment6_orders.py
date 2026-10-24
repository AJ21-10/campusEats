from contextlib import nullcontext
from decimal import Decimal

from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app, rate_buckets


AUTH = {"Authorization": "Bearer assignment-test"}


def setup_function():
    rate_buckets.clear()


def test_order_validation_collects_quantity_and_missing_address_errors():
    response = TestClient(app).post(
        "/orders",
        json={
            "user_id": 1,
            "items": [{"item_id": 4, "qty": 0}],
            "payment_method_id": 2,
            "fulfilment_type": "PICKUP",
            "idempotency_key": "invalid-validation",
        },
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json; charset=utf-8"
    assert response.json()["type"] == "validation-failed"
    assert response.json()["errors"] == [
        {"field": "items[0].qty", "reason": "must be an integer >= 1"},
        {"field": "address", "reason": "must be a non-empty address"},
    ]


def test_address_is_required_even_when_location_id_is_present(monkeypatch):
    def unexpected_transaction():
        raise AssertionError("address validation must precede database work")

    monkeypatch.setattr(api_main, "transaction", unexpected_transaction)
    response = TestClient(app).post(
        "/orders",
        headers=AUTH,
        json={
            "user_id": 1,
            "items": [{"item_id": 4, "qty": 1}],
            "location_id": 1,
            "payment_method_id": 2,
            "fulfilment_type": "PICKUP",
            "idempotency_key": "missing-address",
        },
    )

    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "address", "reason": "must be a non-empty address"}
    ]


def test_order_quantity_rejects_integer_strings_and_floats():
    for invalid_quantity in ("2", 1.5):
        response = TestClient(app).post(
            "/orders",
            json={
                "user_id": 1,
                "items": [{"item_id": 4, "qty": invalid_quantity}],
                "location_id": 1,
                "address": "Campus pickup",
                "payment_method_id": 2,
                "fulfilment_type": "PICKUP",
                "idempotency_key": "invalid-quantity",
            },
        )

        assert response.status_code == 422
        assert response.json()["errors"][0] == {
            "field": "items[0].qty",
            "reason": "must be an integer >= 1",
        }


def test_empty_cart_and_malformed_json_are_problem_details():
    client = TestClient(app)
    empty_cart = client.post(
        "/orders",
        json={
            "user_id": 1,
            "items": [],
            "location_id": 1,
            "address": "Campus pickup",
            "payment_method_id": 2,
            "fulfilment_type": "PICKUP",
            "idempotency_key": "empty-cart",
        },
    )
    malformed = client.post(
        "/orders",
        content=b'{"items":',
        headers={"Content-Type": "application/json"},
    )

    assert empty_cart.status_code == 422
    assert empty_cart.json()["type"] == "empty-cart"
    assert malformed.status_code == 400
    assert malformed.headers["content-type"] == "application/problem+json; charset=utf-8"


def test_unknown_route_and_bad_accept_use_problem_details():
    client = TestClient(app)
    not_found = client.get("/not-a-route")
    not_acceptable = client.get("/orders/1", headers={"Accept": "text/html"})

    assert not_found.status_code == 404
    assert not_found.headers["content-type"] == "application/problem+json; charset=utf-8"
    assert not_acceptable.status_code == 406
    assert not_acceptable.json()["type"] == "not-acceptable"


def test_order_xml_and_json_negotiation(monkeypatch):
    row = (1, 1, 3, None, "PICKUP", None, "PENDING_PAYMENT", Decimal("4.50"), Decimal("4.50"))
    monkeypatch.setattr(api_main, "fetch_one", lambda *_: row)
    client = TestClient(app)

    json_response = client.get("/orders/1", headers=AUTH)
    xml_response = client.get("/orders/1", headers={**AUTH, "Accept": "application/xml"})

    assert json_response.status_code == 200
    assert json_response.headers["content-type"] == "application/json; charset=utf-8"
    assert xml_response.status_code == 200
    assert xml_response.headers["content-type"] == "application/xml; charset=utf-8"
    assert xml_response.text.startswith("<order>")
    assert "<order_id>1</order_id>" in xml_response.text


def test_timeout_is_mapped_to_retryable_503_without_leaking_details(monkeypatch):
    def fail_with_timeout(*_):
        raise TimeoutError("private upstream detail")

    monkeypatch.setattr(api_main, "fetch_one", fail_with_timeout)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/orders/1", headers=AUTH)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "3"
    assert response.headers["content-type"] == "application/problem+json; charset=utf-8"
    assert "private upstream detail" not in response.text
    assert response.json()["type"] == "service-unavailable"
    assert response.json()["detail"] == "A required service is temporarily unavailable"


def test_unexpected_error_is_logged_and_hidden_from_client(monkeypatch):
    def fail_with_database_detail(*_):
        raise RuntimeError("private SQL detail from the database")

    monkeypatch.setattr(api_main, "fetch_one", fail_with_database_detail)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/orders/1", headers=AUTH)

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json; charset=utf-8"
    assert "private SQL detail" not in response.text
    assert response.json()["detail"] == "An unexpected error occurred"
    assert response.json()["type"] == "internal-error"


def test_patch_rejects_illegal_transition(monkeypatch):
    current = (1, 1, 3, None, "PICKUP", None, "PENDING_PAYMENT", Decimal("4.50"), Decimal("4.50"))
    monkeypatch.setattr(api_main, "fetch_one", lambda *_: current)
    response = TestClient(app).patch(
        "/orders/1?user_id=1",
        headers=AUTH,
        json={"status": "COMPLETED"},
    )

    assert response.status_code == 409
    assert response.json()["type"] == "illegal-transition"


def test_delete_cancels_order_and_is_idempotent(monkeypatch):
    class FakeConnection:
        status = "PENDING_PAYMENT"

        def execute(self, query, params=()):
            if query.startswith("UPDATE orders.orders"):
                self.row = (params[0],) if self.status in {"PENDING_PAYMENT", "PLACED"} else None
                if self.row:
                    self.status = "CANCELLED"
                return self
            self.row = (self.status,) if params[0] == 91 else None
            return self

        def fetchone(self):
            return self.row

    connection = FakeConnection()
    monkeypatch.setattr(api_main, "transaction", lambda: nullcontext(connection))
    client = TestClient(app)

    first = client.delete("/orders/91?user_id=1", headers=AUTH)
    replay = client.delete("/orders/91?user_id=1", headers=AUTH)

    assert first.status_code == replay.status_code == 204
    assert first.headers["content-type"] == "application/json; charset=utf-8"


def test_idempotency_replays_creation_response_and_does_not_insert_twice(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.order = None
            self.order_insert_count = 0
            self.item_insert_count = 0

        def execute(self, query, params=()):
            if "WHERE user_id=%s AND idempotency_key=%s" in query:
                return self
            if "FROM accounts.campus_locations" in query:
                self.row = (params[0],)
                return self
            if "FROM catalogue.menu_items" in query:
                self.row = ("Meal", Decimal("4.50"), True, 8)
                return self
            if "INSERT INTO orders.orders" in query:
                self.order_insert_count += 1
                self.order = (91, 1, 8, None, "PICKUP", None, "PENDING_PAYMENT", Decimal("4.50"), Decimal("4.50"))
                self.row = self.order
                return self
            if "INSERT INTO orders.order_items" in query:
                self.item_insert_count += 1
                self.row = None
                return self
            raise AssertionError(f"Unexpected query: {query}")

        def fetchone(self):
            if "idempotency_key" in getattr(self, "last_query", ""):
                return self.order
            return getattr(self, "row", None)

    connection = FakeConnection()
    original_execute = connection.execute

    def execute(query, params=()):
        connection.last_query = query
        if "WHERE user_id=%s AND idempotency_key=%s" in query:
            connection.row = connection.order
            return connection
        return original_execute(query, params)

    connection.execute = execute
    monkeypatch.setattr(api_main, "transaction", lambda: nullcontext(connection))
    client = TestClient(app)
    headers = {**AUTH, "Idempotency-Key": "same-request"}
    body = {
        "user_id": 1,
        "items": [{"item_id": 5, "qty": 1}],
        "location_id": 1,
        "address": "Campus pickup",
        "payment_method_id": 2,
        "fulfilment_type": "PICKUP",
    }

    first = client.post("/orders", json=body, headers=headers)
    connection.order = tuple(connection.order[:6]) + ("PLACED",) + tuple(connection.order[7:])
    replay = client.post("/orders", json=body, headers=headers)

    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert first.headers["Location"] == replay.headers["Location"] == "/orders/91"
    assert first.headers["ETag"] == replay.headers["ETag"]
    assert connection.order_insert_count == 1
    assert connection.item_insert_count == 1


def test_invalid_order_does_not_open_transaction(monkeypatch):
    def unexpected_transaction():
        raise AssertionError("invalid input must be rejected before database work")

    monkeypatch.setattr(api_main, "transaction", unexpected_transaction)
    response = TestClient(app).post(
        "/orders",
        headers=AUTH,
        json={
            "user_id": 1,
            "items": [{"item_id": 4, "qty": -1}],
            "location_id": 1,
            "address": "Campus pickup",
            "payment_method_id": 2,
            "fulfilment_type": "PICKUP",
            "idempotency_key": "not-consumed",
        },
    )

    assert response.status_code == 422


def test_overlong_idempotency_header_is_rejected_before_database_work(monkeypatch):
    def unexpected_transaction():
        raise AssertionError("an invalid idempotency key must not consume or open a transaction")

    monkeypatch.setattr(api_main, "transaction", unexpected_transaction)
    response = TestClient(app).post(
        "/orders",
        headers={**AUTH, "Idempotency-Key": "k" * 101},
        json={
            "user_id": 1,
            "items": [{"item_id": 4, "qty": 1}],
            "address": "Campus pickup",
            "location_id": 1,
            "payment_method_id": 2,
            "fulfilment_type": "PICKUP",
        },
    )

    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "Idempotency-Key", "reason": "must be at most 100 characters"}
    ]
