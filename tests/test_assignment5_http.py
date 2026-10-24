import asyncio
from types import SimpleNamespace

from starlette.responses import Response

from api.main import app, http_policy, rate_buckets
from api.services.orders.router import router as orders_router


def setup_function():
    rate_buckets.clear()


async def ok_response(_):
    return Response(status_code=200)


def test_options_exposes_methods_and_cors_headers(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://student.example")
    request = SimpleNamespace(method="OPTIONS", headers={"Origin": "https://student.example"}, client=SimpleNamespace(host="test"), scope={})
    response = asyncio.run(http_policy(request, ok_response))
    assert response.status_code == 204
    assert "POST" in response.headers["Allow"]
    assert response.headers["Access-Control-Allow-Origin"] == "https://student.example"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_options_allows_local_frontend_on_port_5500(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    request = SimpleNamespace(
        method="OPTIONS",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
        client=SimpleNamespace(host="test"),
        scope={},
    )

    response = asyncio.run(http_policy(request, ok_response))

    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5500"


def test_unsupported_accept_returns_406():
    request = SimpleNamespace(method="GET", headers={"Accept": "text/html"}, client=SimpleNamespace(host="test"), scope={})
    response = asyncio.run(http_policy(request, ok_response))
    assert response.status_code == 406
    assert response.headers["content-type"].startswith("application/problem+json; charset=utf-8")


def test_rate_limit_is_per_client():
    for _ in range(60):
        request = SimpleNamespace(method="GET", headers={"X-Client-ID": "client-a"}, client=SimpleNamespace(host="test"), scope={})
        response = asyncio.run(http_policy(request, ok_response))
        assert response.status_code == 200
    limited_request = SimpleNamespace(method="GET", headers={"X-Client-ID": "client-a"}, client=SimpleNamespace(host="test"), scope={})
    other_request = SimpleNamespace(method="GET", headers={"X-Client-ID": "client-b"}, client=SimpleNamespace(host="test"), scope={})
    limited = asyncio.run(http_policy(limited_request, lambda _: None))
    other = asyncio.run(http_policy(other_request, ok_response))
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
    assert limited.headers["content-type"].startswith("application/problem+json; charset=utf-8")
    assert other.status_code == 200


def test_order_routes_use_crud_and_subresource_verbs():
    routes = {(route.path, tuple(sorted(route.methods or []))) for route in orders_router.routes}
    assert ("/orders", ("POST",)) in routes
    assert ("/orders/{order_id}", ("DELETE",)) in routes
    assert ("/orders/{order_id}", ("GET",)) in routes
    assert ("/orders/{order_id}", ("PATCH", "PUT")) in routes
    assert ("/orders/{order_id}/cancel", ("POST",)) in routes
