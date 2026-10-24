# Assignment 6 Notes

## 1. Status map

- `POST /orders`: **201** created/replayed; **400** malformed JSON; **401** missing bearer; **406** unsupported `Accept`; **409** item unavailable; **422** empty cart or invalid fields; **429** rate limit; **500** unexpected error; **503** database/timeout unavailability.
- `GET /orders/{order_id}`: **200** order representation; **304** matching `If-None-Match`; **401** missing bearer; **404** unknown order; **406** unsupported representation; **422** invalid path/query values; **429** rate limit; **500** unexpected error; **503** database/timeout unavailability.
- `PATCH /orders/{order_id}` and `PUT /orders/{order_id}`: **200** accepted status transition; **401** missing bearer; **404** unknown order; **406** unsupported `Accept`; **409** illegal transition; **412** stale `If-Match`; **422** invalid status/parameters; **429** rate limit; **500** unexpected error; **503** database/timeout unavailability.
- `DELETE /orders/{order_id}`: **204** cancelled or already cancelled; **401** missing bearer; **404** unknown order; **406** unsupported `Accept`; **409** order cannot be cancelled from its current state; **422** invalid parameters; **429** rate limit; **500** unexpected error; **503** database/timeout unavailability.
- `POST /orders/cart/items`: **201** item added; **406** unsupported `Accept`; **409** item unavailable; **422** invalid body; **429** rate limit; **500** unexpected error; **503** database/timeout unavailability.
- `POST /orders/{order_id}/cancel` (legacy): **200** cancelled/already cancelled; **401** missing bearer; **404** unknown order; **406** unsupported `Accept`; **409** illegal cancellation; **422** invalid parameters; **429** rate limit; **500** unexpected error; **503** database/timeout unavailability.
- `GET /orders` is not implemented; the existing collection supports `POST /orders` only.
- **402 Payment Required** is not currently reachable from order creation: the existing Orders workflow does not call a payment processor, and the current charge route records a captured payment rather than simulating a decline. It is not advertised as a reachable order response.
- Illegal transitions use **409 Conflict**, not 422: the request is syntactically valid but conflicts with the resource's current workflow state.

## 2. Problem type catalogue

Problem `type` values use stable plain slugs (not API keys or credentials).

| Type slug | Trigger |
| --- | --- |
| `empty-cart` | Order request has an empty `items` array. |
| `item-unavailable` | Requested menu item does not exist or is not available. |
| `payment-declined` | Reserved for a real declined-payment outcome; not currently reachable in the existing workflow. |
| `order-not-found` | Order ID does not identify an order visible to the request. |
| `illegal-transition` | Requested order status transition or cancellation is not allowed. |
| `validation-failed` | Malformed JSON or request fields fail validation. |
| `rate-limited` | Client exceeded the request rate limit. |
| `not-acceptable` | `Accept` does not include a representation supported by the operation. |
| `internal-error` | Unexpected exception; details are logged server-side only. |
| `service-unavailable` | Database or downstream timeout/connection failure; retry guidance is returned. |
| `not-found` | Unknown URL outside the Orders resource. |
| `unauthorized` | Required bearer header is absent or malformed. |
| `precondition-failed` | `If-Match` does not equal the current ETag. |

## 3. Real Problem Details example

The service returned this body for an order with `qty: 0` and no saved address reference:

```json
{
  "type": "validation-failed",
  "title": "Validation failed",
  "status": 422,
  "detail": "Request validation failed",
  "instance": "/orders",
  "errors": [
    {
      "field": "items[0].qty",
      "reason": "must be an integer >= 1"
    },
    {
      "field": "address",
      "reason": "must be a non-empty address"
    }
  ]
}
```

- `type`: stable problem identifier.
- `title`: short human-readable summary.
- `status`: HTTP status, 422.
- `detail`: safe request-specific summary.
- `instance`: request path.
- `errors`: all detected field-level validation errors.

## 4. Two-field validation response

The request used `items: [{"item_id": 1, "qty": 0}]` and omitted both `address` and `location_id`. This real response reports both invalid fields at once:

```json
{
  "type": "validation-failed",
  "title": "Validation failed",
  "status": 422,
  "detail": "Request validation failed",
  "instance": "/orders",
  "errors": [
    {
      "field": "items[0].qty",
      "reason": "must be an integer >= 1"
    },
    {
      "field": "address",
      "reason": "must be a non-empty address"
    }
  ]
}
```

## 5. Retry safety

- `GET /orders/{order_id}` is safe and idempotent; retry transient **429**/**503** responses after `Retry-After`, or after a network timeout. `If-None-Match` can avoid retransmitting an unchanged representation.
- `PUT` is idempotent when repeated with the same status. `DELETE` is idempotent: after the first cancellation, repeating it returns 204. Retry these only for transient failures, respecting `Retry-After`.
- `PATCH` is not generally guaranteed idempotent across different current order states; use it only to set the intended same status and respect `If-Match`.
- `POST /orders` may be retried only with the same `Idempotency-Key` (or body key); replay returns 201 and the same creation body, ETag, and `Location` without another order/item insert.
- Retry **429**, **503**, and transport timeouts only; honor `Retry-After` when present. Do not retry an unchanged 4xx request. The API adds `Retry-After` on both 429 and 503 responses.

## 6. Internal-error handling

The global exception handler logs the real exception and stack trace on the server, then returns a generic 500 response. A regression test injected a `RuntimeError` containing `private SQL detail from the database`; the client received:

```json
{
  "type": "internal-error",
  "title": "Internal server error",
  "status": 500,
  "detail": "An unexpected error occurred",
  "instance": "/orders/1"
}
```

This is intentionally HTTP **500**, not a 4xx client error: an internal failure must not be misrepresented as a client mistake. SQL text, stack traces, file paths, and library names are hidden from the response. A simulated timeout and actual database connection failure map to 503 with `Retry-After`.

## 7. JSON and XML negotiation

The same persisted order (`order_id: 13`) returned **200** with `Accept: application/json` and **200** with `Accept: application/xml`. These bodies are copied from the D3 curl transcript:

`Accept: application/json`

```json
{"order_id":13,"user_id":14,"restaurant_id":1,"location_id":null,"fulfilment_type":"PICKUP","scheduled_at":null,"status":"PENDING_PAYMENT","subtotal":95.0,"total":95.0}
```

`Accept: application/xml`

```xml
<order><order_id>13</order_id><user_id>14</user_id><restaurant_id>1</restaurant_id><location_id /><fulfilment_type>PICKUP</fulfilment_type><scheduled_at /><status>PENDING_PAYMENT</status><subtotal>95.00</subtotal><total>95.00</total></order>
```
