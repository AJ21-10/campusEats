import json
import os
import random
import time
from urllib import error as urllib_error
from urllib import request as urllib_request

from flask import Flask, jsonify, request

from delivery.errors import problem
from delivery.store import store

app = Flask(__name__)


def validate_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    required = ["order_id", "student_id", "pickup_location", "dropoff_location"]
    for key in required:
        if key not in payload:
            raise ValueError(f"Missing required field: {key}")
    if not isinstance(payload["order_id"], str) or not payload["order_id"].strip():
        raise ValueError("order_id must be a non-empty string")
    if not isinstance(payload["student_id"], str) or not payload["student_id"].strip():
        raise ValueError("student_id must be a non-empty string")
    if not isinstance(payload["pickup_location"], str) or len(payload["pickup_location"].strip()) < 2:
        raise ValueError("pickup_location must be at least 2 characters")
    if not isinstance(payload["dropoff_location"], str) or len(payload["dropoff_location"].strip()) < 2:
        raise ValueError("dropoff_location must be at least 2 characters")


def validate_status_request(payload):
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    if "status" not in payload:
        raise ValueError("Missing required field: status")
    status = payload["status"]
    if status not in {"assigned", "picked_up", "delivered"}:
        raise ValueError("status must be one of: assigned, picked_up, delivered")


def payment_verification(order_id):
    url = os.environ.get("PAYMENTS_SERVICE_URL")
    if not url:
        raise RuntimeError("PAYMENTS_SERVICE_URL is not configured")

    payload = {"order_id": order_id, "status": "verified"}
    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

    for attempt in range(1, 4):
        try:
            with urllib_request.urlopen(req, timeout=2) as resp:
                body = resp.read()
                return body.decode("utf-8")
        except urllib_error.HTTPError as exc:
            raise RuntimeError(f"Payment service rejected request: {exc.code}")
        except (urllib_error.URLError, TimeoutError, OSError):
            if attempt == 3:
                raise RuntimeError("Payment service unreachable")
            time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.5))
    raise RuntimeError("Payment verification failed")


@app.errorhandler(400)
def handle_bad_request(error):
    payload, status = problem("invalid-request", "Invalid request", 400, str(error))
    return jsonify(payload), status


@app.errorhandler(404)
def handle_not_found(error):
    payload, status = problem("not-found", "Not found", 404, "Resource not found")
    return jsonify(payload), status


@app.errorhandler(409)
def handle_conflict(error):
    payload, status = problem("state-conflict", "Conflict", 409, str(error))
    return jsonify(payload), status


@app.errorhandler(422)
def handle_unprocessable(error):
    payload, status = problem("domain-rejected", "Unprocessable entity", 422, str(error))
    return jsonify(payload), status


@app.route("/deliveries", methods=["POST"])
def create_delivery():
    try:
        payload = request.get_json(force=False, silent=True)
        validate_payload(payload)
    except ValueError as exc:
        body, status = problem("invalid-request", "Invalid request", 400, str(exc))
        return jsonify(body), status

    idempotency = request.headers.get("Idempotency-Key")
    if idempotency and idempotency in store._idempotency:
        delivery_id = store._idempotency[idempotency]
        record = store.get(delivery_id)
        response = jsonify(record.as_json())
        response.status_code = 201
        response.headers["Location"] = f"/deliveries/{delivery_id}"
        return response

    try:
        payment_verification(payload["order_id"])
    except RuntimeError:
        body, status = problem("dependency-unreachable", "Payment verification unavailable", 422, "Payments service is unavailable")
        return jsonify(body), status

    record, delivery_id = store.create(payload, idempotency)
    response = jsonify(record.as_json())
    response.status_code = 201
    response.headers["Location"] = f"/deliveries/{delivery_id}"
    return response


@app.route("/deliveries", methods=["GET"])
def list_deliveries():
    order_id = request.args.get("order_id")
    items = store.list(order_id)
    return jsonify([record.as_json() for record in items]), 200


@app.route("/deliveries/<delivery_id>", methods=["GET"])
def get_delivery(delivery_id):
    record = store.get(delivery_id)
    if record is None:
        body, status = problem("not-found", "Not found", 404, f"Delivery {delivery_id} not found")
        return jsonify(body), status
    return jsonify(record.as_json()), 200


@app.route("/deliveries/<delivery_id>/status", methods=["PUT"])
def update_delivery_status(delivery_id):
    record = store.get(delivery_id)
    if record is None:
        body, status = problem("not-found", "Not found", 404, f"Delivery {delivery_id} not found")
        return jsonify(body), status

    try:
        payload = request.get_json(force=False, silent=True)
        validate_status_request(payload)
    except ValueError as exc:
        body, status = problem("invalid-request", "Invalid request", 400, str(exc))
        return jsonify(body), status

    try:
        updated = store.update_status(delivery_id, payload["status"])
    except ValueError:
        body, status = problem("state-conflict", "Conflict", 409, "Status transition is not allowed")
        return jsonify(body), status

    return jsonify(updated.as_json()), 202


if __name__ == "__main__":
    app.run(debug=True)
