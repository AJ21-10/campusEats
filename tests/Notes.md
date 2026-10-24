Team 15 :
Team Lead : Anurag Panda 20251651026
Members : i) Taj Ansari 20251651095
ii) Dinesh Kushwaha 20251651035
iii)Rohit 20251651079
iv) Pushpender 20251651074

## Assignment 5 — FastAPI HTTP Methods and Headers

The active implementation is the PostgreSQL-backed FastAPI application in `api/`. The hidden `.delivery/` directory is intentionally preserved unchanged.

### 1. CampusEats Method Map

| Action                                | Method    | URL                                                  |
| ------------------------------------- | --------- | ---------------------------------------------------- |
| Register account                      | POST      | `/accounts/register`                                 |
| Log in                                | POST      | `/accounts/login`                                    |
| Read profile                          | GET       | `/accounts/{user_id}/profile`                        |
| Replace profile                       | PUT       | `/accounts/{user_id}/profile`                        |
| Add location                          | POST      | `/accounts/{user_id}/locations`                      |
| Read location                         | GET       | `/accounts/{user_id}/locations/{location_id}`        |
| Catalogue queries and mutations       | POST      | `/catalogue/graphql`                                 |
| Add cart item                         | POST      | `/orders/cart/items`                                 |
| Create order                          | POST      | `/orders`                                            |
| Read order                            | GET       | `/orders/{order_id}?user_id=`                        |
| Replace/partially update order status | PUT/PATCH | `/orders/{order_id}?user_id=`                        |
| Cancel order                          | POST      | `/orders/{order_id}/cancel?user_id=`                 |
| Charge payment                        | POST      | `/payments/charge`                                   |
| Read payment                          | GET       | `/payments/{payment_reference}`                      |
| Refund payment                        | POST      | `/payments/{payment_reference}/refund`               |
| Create fulfilment                     | POST      | `/delivery/fulfilments`                              |
| Assign delivery                       | POST      | `/delivery/fulfilments/{fulfilment_id}/assign`       |
| Read fulfilment                       | GET       | `/delivery/fulfilments/{fulfilment_id}`              |
| Create notification/review            | POST      | `/engagement/notifications` or `/engagement/reviews` |
| List notifications                    | GET       | `/engagement/notifications/{user_id}`                |

Catalogue reads use GraphQL queries (`restaurants`, `restaurant`, and `menuItem`); catalogue writes use mutations (`createRestaurant`, `createMenu`, and `addMenuItem`). Order and payment workflows remain REST sub-resources.

### 2. Safe and Idempotent Analysis

GET endpoints are safe and idempotent because they only read. PUT is idempotent when the same representation is sent repeatedly. POST creates and workflow actions are neither generally safe nor idempotent. Order creation accepts `Idempotency-Key` and the database unique constraint `(user_id, idempotency_key)` prevents duplicate orders. `If-None-Match` makes an unchanged order read retryable, while `If-Match` prevents stale order writes.

| Endpoint                 | Method    | Safe? | Idempotent?              | Reason                                                           |
| ------------------------ | --------- | ----- | ------------------------ | ---------------------------------------------------------------- |
| `/catalogue/graphql`     | POST      | Yes for queries | Depends on operation | GraphQL queries read; mutations change catalogue state           |
| `/orders/{id}`           | GET       | Yes   | Yes                      | Read-only and conditional with ETag                              |
| `/orders/{id}`           | PUT/PATCH | No    | PUT: yes, PATCH: depends | Changes status; `If-Match` prevents stale overwrite              |
| `/orders`                | POST      | No    | No by default            | Creation has a side effect; `Idempotency-Key` makes retries safe |
| `/orders/{id}/cancel`    | POST      | No    | No                       | Workflow transition changes state                                |

### 3. Complete HTTP Exchange

Request:

```http
POST /orders HTTP/1.1
Host: localhost:8000
Content-Type: application/json
Accept: application/json
Authorization: Bearer assignment-token
Idempotency-Key: order-abc-123

{"user_id":1,"items":[{"item_id":7,"quantity":2}],"payment_method_id":3,"fulfilment_type":"PICKUP","idempotency_key":"order-abc-123"}
```

Response:

```http
HTTP/1.1 201 Created
Content-Type: application/json
Location: /orders/42?user_id=1
ETag: "order-version-hash"
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-Content-Type-Options: nosniff

{"order_id":42,"status":"PENDING_PAYMENT","user_id":1}
```

### 4. Headers Table

| Endpoint                 | Request headers                                                             | Response headers                                                                 |
| ------------------------ | --------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `POST /orders`           | `Content-Type`, `Accept`, `Authorization`, `Idempotency-Key`                | `Content-Type`, `Location`, `ETag`, rate-limit headers, `X-Content-Type-Options` |
| `GET /orders/{id}`       | `Accept`, `Authorization`, optional `If-None-Match`                         | `Content-Type`, `ETag`, `Cache-Control`, rate-limit headers                      |
| `PUT/PATCH /orders/{id}` | `Content-Type`, `Accept`, `Authorization`, optional `If-Match`              | `Content-Type`, `ETag`, rate-limit headers                                       |
| `OPTIONS /{resource}`    | `Origin`, `Access-Control-Request-Method`, `Access-Control-Request-Headers` | `204`, `Allow`, CORS preflight headers                                           |
| Any JSON endpoint        | optional `X-Client-ID`                                                      | `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-Content-Type-Options`           |

### 5. Safe-Retry Plan

| Endpoint                 | Safe? | Idempotent? | Retry mechanism   | Reason                                           |
| ------------------------ | ----- | ----------- | ----------------- | ------------------------------------------------ |
| `GET /orders/{id}`       | Yes   | Yes         | `If-None-Match`   | Avoids retransmitting an unchanged body with 304 |
| `PUT/PATCH /orders/{id}` | No    | PUT: yes    | `If-Match`        | Rejects stale editors with 412                   |
| `POST /orders`           | No    | No          | `Idempotency-Key` | Prevents duplicate order creation                |

### 6. Assignment Questions

**Question 1.** `GET /orders/{id}` returns 200 and its important header is `ETag`, which identifies the exact representation for caching and conditional reads. `POST /orders` returns 201 and its important header is `Location`, which identifies the newly created order. `DELETE`-style removal returns 204 and its important header is `X-Content-Type-Options: nosniff`, which prevents MIME sniffing on error or empty responses.

**Question 2.** GET is safe and idempotent. PUT is idempotent but not safe. POST creation and cancellation are neither. Order creation is retry-safe through `Idempotency-Key` and the database uniqueness constraint.

**Question 3.** A response may contain `ETag: "abc123"`. `GET /orders/42` with `If-None-Match: "abc123"` returns 304 with no body. `PUT /orders/42` with an old `If-Match: "old"` returns 412. These save an unnecessary transfer and prevent lost updates respectively.

**Question 4.** A valid JSON order with `fulfilment_type=DELIVERY` and no `location_id` produces 422 because it violates a domain rule. Malformed JSON or a missing required field produces 400 because the request cannot be interpreted as a valid request.

**Question 5.** The browser enforces CORS and can block JavaScript access even when the server logs 200. `Access-Control-Allow-Origin` tells the browser that the configured origin may read the response.

**Question 6.** A single order response uses `Cache-Control: private, max-age=0, must-revalidate` because it is user-specific but conditionally cacheable. A login or payment response should use `Cache-Control: no-store` because credentials and payment details must not be retained by caches.

**Question 7.** POST is appropriate for complex searches with a large structured filter, sensitive criteria, or a request body too large for a URI. Switching loses bookmarkability, broad cache/proxy support, easy curl reproduction, and the conventional safe/read-only semantics of GET.

**Question 8.** With 201, `Location` points to the newly created resource. With a 3xx response, it points to the URI the client should retrieve or follow next.

### 7. Validation and limitations

FastAPI publishes the active contract at `/openapi.json`. The original Assignment 4 OpenAPI and curl transcript are under the protected `.delivery/` directory and were not modified. Database-backed endpoint tests require PostgreSQL initialized from `schema.sql`; app import and route compilation were verified locally.
