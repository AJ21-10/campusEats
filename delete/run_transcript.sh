#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$ROOT"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TEST_USER_ID="${TEST_USER_ID:-14}"
TEST_LOCATION_ID="${TEST_LOCATION_ID:-1}"
TEST_ITEM_ID="${TEST_ITEM_ID:-1}"
TEST_KEY="a6-transcript-$(date +%s)-$$"
AUTH_HEADER="Authorization: Bearer assignment-transcript"
ORDER_ID=""
AUTH_HEADER="Authorization: Bearer assignment6-transcript-token"
TIMEOUT_PID=""
TIMEOUT_LOG=""

if [[ -x "$ROOT/.venv/bin/uvicorn" ]]; then
  UVICORN_BIN="$ROOT/.venv/bin/uvicorn"
else
  UVICORN_BIN="${UVICORN_BIN:-uvicorn}"
fi
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python}"
fi

cleanup() {
  if [[ -n "$TIMEOUT_PID" ]]; then
    kill "$TIMEOUT_PID" 2>/dev/null || true
    wait "$TIMEOUT_PID" 2>/dev/null || true
  fi
  if [[ -n "$TIMEOUT_LOG" ]]; then
    rm -f -- "$TIMEOUT_LOG"
  fi
  if [[ -n "$ORDER_ID" ]]; then
    TEST_USER_ID="$TEST_USER_ID" TEST_KEY="$TEST_KEY" PYTHONPATH="$ROOT" "$PYTHON_BIN" - >/dev/null <<'PY'
import os
from api.db import transaction

with transaction() as conn:
    order = conn.execute(
        "SELECT order_id FROM orders.orders WHERE user_id=%s AND idempotency_key=%s",
        (int(os.environ["TEST_USER_ID"]), os.environ["TEST_KEY"]),
    ).fetchone()
    if order:
        conn.execute("DELETE FROM orders.order_items WHERE order_id=%s", (order[0],))
        conn.execute(
            "DELETE FROM orders.orders WHERE order_id=%s AND user_id=%s AND idempotency_key=%s",
            (order[0], int(os.environ["TEST_USER_ID"]), os.environ["TEST_KEY"]),
        )
PY
  fi
}
trap cleanup EXIT

exec >"$ROOT/transcript.txt"

section() {
  printf '\n===== %s =====\n' "$1"
}

command_line() {
  printf '$ %s\n' "$1"
}

ORDER_BODY="$(printf '{"user_id":%s,"items":[{"item_id":%s,"qty":1}],"address":"Campus pickup","location_id":%s,"payment_method_id":1,"fulfilment_type":"PICKUP"}' "$TEST_USER_ID" "$TEST_ITEM_ID" "$TEST_LOCATION_ID")"

section "D1 - Create an order (201 + Location) and GET the Location"
command_line "curl -i -X POST '$BASE_URL/orders' -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Bearer <redacted>' -H 'Idempotency-Key: <generated>' -d '$ORDER_BODY'"
CREATED="$(curl -sS -i --max-time 10 -X POST "$BASE_URL/orders" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H "$AUTH_HEADER" \
  -H "Idempotency-Key: $TEST_KEY" \
  -d "$ORDER_BODY")"
printf '%s\n' "$CREATED"
LOCATION="$(printf '%s\n' "$CREATED" | awk 'tolower($1) == "location:" {print $2; exit}' | tr -d '\r')"
if [[ -z "$LOCATION" ]]; then
  printf 'The order creation response did not include Location; transcript generation stopped.\n' >&2
  exit 1
fi
ORDER_ID="${LOCATION##*/}"
command_line "curl -i '$BASE_URL$LOCATION' -H 'Authorization: Bearer <redacted>'"
curl -sS -i --max-time 10 "$BASE_URL$LOCATION" -H "$AUTH_HEADER"

section "D2 - Empty cart"
command_line "curl -i -X POST '$BASE_URL/orders' -H 'Content-Type: application/json' -H 'Authorization: Bearer <redacted>' -H 'Idempotency-Key: transcript-empty-cart' -d '{\"user_id\":$TEST_USER_ID,\"items\":[],\"address\":\"Campus pickup\",\"location_id\":$TEST_LOCATION_ID,\"payment_method_id\":1,\"fulfilment_type\":\"PICKUP\"}'"
curl -sS -i --max-time 10 -X POST "$BASE_URL/orders" \
  -H 'Content-Type: application/json' -H "$AUTH_HEADER" \
  -H 'Idempotency-Key: transcript-empty-cart' \
  -d "{\"user_id\":$TEST_USER_ID,\"items\":[],\"address\":\"Campus pickup\",\"location_id\":$TEST_LOCATION_ID,\"payment_method_id\":1,\"fulfilment_type\":\"PICKUP\"}"

section "D2 - Quantity zero"
command_line "curl -i -X POST '$BASE_URL/orders' -H 'Content-Type: application/json' -H 'Authorization: Bearer <redacted>' -H 'Idempotency-Key: transcript-qty-zero' -d '{\"user_id\":$TEST_USER_ID,\"items\":[{\"item_id\":$TEST_ITEM_ID,\"qty\":0}],\"address\":\"Campus pickup\",\"location_id\":$TEST_LOCATION_ID,\"payment_method_id\":1,\"fulfilment_type\":\"PICKUP\"}'"
curl -sS -i --max-time 10 -X POST "$BASE_URL/orders" \
  -H 'Content-Type: application/json' -H "$AUTH_HEADER" \
  -H 'Idempotency-Key: transcript-qty-zero' \
  -d "{\"user_id\":$TEST_USER_ID,\"items\":[{\"item_id\":$TEST_ITEM_ID,\"qty\":0}],\"address\":\"Campus pickup\",\"location_id\":$TEST_LOCATION_ID,\"payment_method_id\":1,\"fulfilment_type\":\"PICKUP\"}"

section "D2 - Negative quantity"
command_line "curl -i -X POST '$BASE_URL/orders' -H 'Content-Type: application/json' -H 'Authorization: Bearer <redacted>' -H 'Idempotency-Key: transcript-qty-negative' -d '{\"user_id\":$TEST_USER_ID,\"items\":[{\"item_id\":$TEST_ITEM_ID,\"qty\":-1}],\"address\":\"Campus pickup\",\"location_id\":$TEST_LOCATION_ID,\"payment_method_id\":1,\"fulfilment_type\":\"PICKUP\"}'"
curl -sS -i --max-time 10 -X POST "$BASE_URL/orders" \
  -H 'Content-Type: application/json' -H "$AUTH_HEADER" \
  -H 'Idempotency-Key: transcript-qty-negative' \
  -d "{\"user_id\":$TEST_USER_ID,\"items\":[{\"item_id\":$TEST_ITEM_ID,\"qty\":-1}],\"address\":\"Campus pickup\",\"location_id\":$TEST_LOCATION_ID,\"payment_method_id\":1,\"fulfilment_type\":\"PICKUP\"}"

section "D2 - Two invalid fields in one request"
command_line "curl -i -X POST '$BASE_URL/orders' -H 'Content-Type: application/json' -H 'Authorization: Bearer <redacted>' -H 'Idempotency-Key: transcript-two-errors' -d '{\"user_id\":$TEST_USER_ID,\"items\":[{\"item_id\":$TEST_ITEM_ID,\"qty\":0}],\"payment_method_id\":1,\"fulfilment_type\":\"PICKUP\"}'"
curl -sS -i --max-time 10 -X POST "$BASE_URL/orders" \
  -H 'Content-Type: application/json' -H "$AUTH_HEADER" \
  -H 'Idempotency-Key: transcript-two-errors' \
  -d "{\"user_id\":$TEST_USER_ID,\"items\":[{\"item_id\":$TEST_ITEM_ID,\"qty\":0}],\"payment_method_id\":1,\"fulfilment_type\":\"PICKUP\"}"

section "D2 - Unknown order ID"
command_line "curl -i '$BASE_URL/orders/2147483647' -H 'Authorization: Bearer <redacted>'"
curl -sS -i --max-time 10 "$BASE_URL/orders/2147483647" -H "$AUTH_HEADER"

section "D2 - Illegal order transition"
command_line "curl -i -X PATCH '$BASE_URL/orders/$ORDER_ID?user_id=$TEST_USER_ID' -H 'Content-Type: application/json' -H 'Authorization: Bearer <redacted>' -d '{\"status\":\"COMPLETED\"}'"
curl -sS -i --max-time 10 -X PATCH "$BASE_URL/orders/$ORDER_ID?user_id=$TEST_USER_ID" \
  -H 'Content-Type: application/json' -H "$AUTH_HEADER" \
  -d '{"status":"COMPLETED"}'

section "D2 - Unavailable item"
printf 'Note: payment decline is not reachable in the existing Orders workflow; see NOTES.md.\n'
command_line "curl -i -X POST '$BASE_URL/orders' -H 'Content-Type: application/json' -H 'Authorization: Bearer <redacted>' -H 'Idempotency-Key: transcript-unavailable-item' -d '{\"user_id\":$TEST_USER_ID,\"items\":[{\"item_id\":999999999,\"qty\":1}],\"address\":\"Campus pickup\",\"location_id\":$TEST_LOCATION_ID,\"payment_method_id\":1,\"fulfilment_type\":\"PICKUP\"}'"
curl -sS -i --max-time 10 -X POST "$BASE_URL/orders" \
  -H 'Content-Type: application/json' -H "$AUTH_HEADER" \
  -H 'Idempotency-Key: transcript-unavailable-item' \
  -d "{\"user_id\":$TEST_USER_ID,\"items\":[{\"item_id\":999999999,\"qty\":1}],\"address\":\"Campus pickup\",\"location_id\":$TEST_LOCATION_ID,\"payment_method_id\":1,\"fulfilment_type\":\"PICKUP\"}"

section "D2 - Rate limit (429 + Retry-After)"
command_line "for _ in \$(seq 1 60); do curl -sS -o /dev/null -H 'X-Client-ID: assignment6-transcript-rate-limit' '$BASE_URL/health'; done; curl -i -H 'X-Client-ID: assignment6-transcript-rate-limit' '$BASE_URL/health'"
for _ in $(seq 1 60); do
  curl -sS --max-time 3 -o /dev/null \
    -H 'X-Client-ID: assignment6-transcript-rate-limit' \
    "$BASE_URL/health"
done
curl -sS -i --max-time 10 -H 'X-Client-ID: assignment6-transcript-rate-limit' "$BASE_URL/health"

section "D2 - Malformed JSON"
command_line "curl -i -X POST '$BASE_URL/orders' -H 'Content-Type: application/json' -H 'Authorization: Bearer <redacted>' --data-binary '{\"user_id\":'"
curl -sS -i --max-time 10 -X POST "$BASE_URL/orders" \
  -H 'Content-Type: application/json' -H "$AUTH_HEADER" \
  --data-binary '{"user_id":'

section "D2 - Unsupported Accept (406)"
command_line "curl -i '$BASE_URL/orders/$ORDER_ID' -H 'Authorization: Bearer <redacted>' -H 'Accept: text/html'"
curl -sS -i --max-time 10 "$BASE_URL/orders/$ORDER_ID" \
  -H "$AUTH_HEADER" -H 'Accept: text/html'

section "D3 - The same order as JSON"
command_line "curl -i '$BASE_URL/orders/$ORDER_ID' -H 'Authorization: Bearer <redacted>' -H 'Accept: application/json'"
curl -sS -i --max-time 10 "$BASE_URL/orders/$ORDER_ID" \
  -H "$AUTH_HEADER" -H 'Accept: application/json'

section "D3 - The same order as XML"
command_line "curl -i '$BASE_URL/orders/$ORDER_ID' -H 'Authorization: Bearer <redacted>' -H 'Accept: application/xml'"
curl -sS -i --max-time 10 "$BASE_URL/orders/$ORDER_ID" \
  -H "$AUTH_HEADER" -H 'Accept: application/xml'

section "D4 - Idempotency replay"
command_line "curl -i -X POST '$BASE_URL/orders' -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Bearer <redacted>' -H 'Idempotency-Key: <same generated key>' -d '$ORDER_BODY'"
curl -sS -i --max-time 10 -X POST "$BASE_URL/orders" \
  -H 'Content-Type: application/json' -H 'Accept: application/json' \
  -H "$AUTH_HEADER" -H "Idempotency-Key: $TEST_KEY" -d "$ORDER_BODY"

section "D4 - Dependency timeout/unavailability maps to 503"
TIMEOUT_LOG="$(mktemp)"
DATABASE_URL='postgresql://127.0.0.1:1/campuseats?connect_timeout=1' \
  PYTHONPATH="$ROOT" "$UVICORN_BIN" api.main:app --host 127.0.0.1 --port 8001 \
  >"$TIMEOUT_LOG" 2>&1 &
TIMEOUT_PID=$!
READY=0
for _ in $(seq 1 40); do
  if curl -fsS --max-time 1 http://127.0.0.1:8001/health >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 0.25
done
if [[ "$READY" != 1 ]]; then
  printf 'The temporary dependency-failure server did not start; transcript generation stopped.\n' >&2
  exit 1
fi
command_line "curl -i 'http://127.0.0.1:8001/health/database'"
curl -sS -i --max-time 5 http://127.0.0.1:8001/health/database
