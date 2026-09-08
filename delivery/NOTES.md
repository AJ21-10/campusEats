# CampusEats Delivery Service — Assignment 4 Notes

Team 15

- Team Lead: Anurag Panda — 20251651026
- Members: Taj Ansari — 20251651095; Dinesh Kushwaha — 20251651035; Rohit — 20251651079; Pushpender — 20251651074

## Part A — Resource table

| Method | URL                              | What it does                                      | Success code | Failure codes      |
| ------ | -------------------------------- | ------------------------------------------------- | ------------ | ------------------ |
| POST   | /deliveries                      | Create a delivery record for an order and student | 201          | 400, 409, 422      |
| GET    | /deliveries                      | List deliveries, optionally filtered by order_id  | 200          | 400                |
| GET    | /deliveries/{delivery_id}        | Read one delivery                                 | 200          | 404                |
| PUT    | /deliveries/{delivery_id}/status | Update the delivery state                         | 202          | 400, 404, 409, 422 |

## Part A5 — Justification for one hard choice

The state transition operation was the least comfortable fit to a REST resource because the real domain behavior is not a simple create or read, but a workflow: a delivery can move from assigned to picked_up to delivered, and invalid transitions must be rejected. I resolved this by exposing it as a sub-resource under the delivery itself, /deliveries/{delivery_id}/status, which makes the lifecycle explicit and keeps the operation tied to the owning resource. I rejected a more general /delivery-statuses collection because that would split one delivery’s transition history across another resource and make the state machine harder to reason about and validate.

## Part B — OpenAPI validation

The OpenAPI document is published in [delivery/openapi.yaml](delivery/openapi.yaml). It was validated with `openapi-spec-validator`, which reported:

`delivery/openapi.yaml: OK`

## Part C — Implementation summary

The delivery service follows the requested Tutorial 4 structure: `models.py`, `store.py`, `errors.py`, `app.py`, and `tests/`.

- `DeliveryRecord` keeps the internal state and exposes `as_json()` to return only the public representation.
- The model differs from the published representation by excluding internal or credential-like fields; no sensitive identifier leaks into the response.
- The create endpoint verifies a valid request body via `validate_payload()` before any field access.
- The status endpoint validates transitions via `validate_status_request()` and `store.update_status()`.
- The single error envelope is built by `problem()` and used across all endpoints.
- The create endpoint supports an `Idempotency-Key` header, storing the key and returning the original resource on repeat requests instead of redoing the payment check or creating a duplicate delivery.

## Part D — Dependency hardening and fallback

The service makes a real outbound HTTP call to the Payments service using an environment variable, `PAYMENTS_SERVICE_URL`, instead of a hard-coded URL. The call is wrapped with a 2-second timeout and a retry loop with exponential backoff plus jitter, and it never retries a 4xx response or a request that is not safe to repeat. The create path enforces the idempotency key for any retried create call so duplicate side effects are avoided.

When the dependency is unreachable, the service does not silently degrade by pretending the payment succeeded. A delivery should not be created without a verified payment signal because that would create a false order state and break trust between service boundaries. The service therefore returns a domain-level 422 with a standard problem body explaining that the dependency is unavailable, exactly preserving the integrity of the order lifecycle.

## Answers to the five questions

1. Count the lines in the Assignment 3 WSDL and in the OpenAPI file. What is the difference actually made of? Name two things the WSDL declared that the OpenAPI file does not need to.

   The repo snapshot available here does not include the original WSDL file needed to count its lines exactly; the current service contract is the OpenAPI file in [delivery/openapi.yaml](delivery/openapi.yaml), which is 208 lines long. The actual difference is not a large conceptual jump, but a change in representation: the WSDL expressed a SOAP contract with protocol-specific messaging details, endpoint shapes, and XML schema constraints, while OpenAPI is a REST resource contract that describes URLs, methods, request bodies, and JSON responses. Two things WSDL declared that OpenAPI does not need to include are the SOAP envelope/message wrapper and the XML Schema definitions for the wire format.

2. Quote one soap:Fault from your Assignment 3 work and show the status code and problem body that replaced it. Why is returning that error inside a 200 OK a problem for the network in between?

   A representative SOAP fault would be:

   ```xml
   <soap:Fault>
     <faultcode>soap:Server</faultcode>
     <faultstring>Payment verification unavailable</faultstring>
   </soap:Fault>
   ```

   The REST replacement is:

   ```json
   {
     "type": "dependency-unreachable",
     "title": "Payment verification unavailable",
     "status": 422,
     "detail": "Payments service is unavailable"
   }
   ```

   Returning an error body inside a 200 OK is a problem because HTTP intermediaries and clients treat 200 as success. A proxy, load balancer, or any network element may cache, treat it as successful, or bypass error handling; the caller never sees it as a failure at the transport layer and may continue with a false success signal.

3. Which of UDDI's three moves — publish, find, bind — still exist in your new setup, and which disappeared? Explain what took over the job.

   In the new setup, the publish step still exists in spirit, but it is no longer a formal UDDI registry step; the service is documented directly in the OpenAPI contract, and its URL is configured in environment variables or deployment metadata. The find step is effectively replaced by direct configuration and service discovery via environment/config management, while bind is replaced by the actual HTTP client call made by the service itself. The registry mechanism disappeared because the REST ecosystem handles discovery and invocation with explicit configuration, load balancers, and API contracts rather than a central UDDI registry.

4. Your XML Schema was enforced before your code ran; your OpenAPI schema is not. Name the specific function in your code that now carries that responsibility, and one failure that would get through if you had not written it.

   The validation responsibility now sits in `validate_payload()` inside [delivery/app.py](delivery/app.py). Without it, a malformed request such as a payload missing `dropoff_location` or a non-string `student_id` could reach the store layer and create inconsistent state or a broken delivery record.

5. Name one part of your service where you would still choose the SOAP stack over REST, and state exactly what guarantee you would be buying. Answering “nowhere” needs a stronger argument than answering “somewhere”.

   I would still choose SOAP for an enterprise-grade payment settlement or auditing workflow. The guarantee I would be buying is strong protocol-level reliability: WS-Security, formal message-level contracts, and a well-defined transaction and fault model for regulated, high-integrity exchanges where every message must be signed, traced, and processed with explicit semantics.

## Files in the service folder

- [delivery/openapi.yaml](delivery/openapi.yaml)
- [delivery/app.py](delivery/app.py)
- [delivery/store.py](delivery/store.py)
- [delivery/models.py](delivery/models.py)
- [delivery/errors.py](delivery/errors.py)
- [delivery/tests/test_api.py](delivery/tests/test_api.py)
