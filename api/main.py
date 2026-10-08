from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
import time
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from passlib.context import CryptContext
import psycopg
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.db import check_connection, fetch_all, fetch_one, transaction
from api.schemas import (
    AssignmentInput, CartItemInput, FulfilmentInput, ItemInput, LocationInput, LoginInput,
    MenuInput, NotificationInput, OrderInput, PaymentInput, ProfileInput,
    RefundInput, RegisterInput, RestaurantInput, ReviewInput, OrderStatusInput, row_dict,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
logger = logging.getLogger(__name__)


class ApiProblem(Exception):
    def __init__(
        self,
        type_: str,
        title: str,
        status_code: int,
        detail: str,
        *,
        errors: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(detail)
        self.type = type_
        self.title = title
        self.status_code = status_code
        self.detail = detail
        self.errors = errors
        self.headers = headers or {}


def request_instance(request: Request | object) -> str:
    url = getattr(request, "url", None)
    if url is not None:
        return str(getattr(url, "path", "/"))
    return "/"


def problem(type_: str, title: str, status_code: int, detail: str, *, instance: str | None = None, errors: list[dict[str, str]] | None = None):
    payload = {
        "type": type_,
        "title": title,
        "status": status_code,
        "detail": detail,
    }
    if instance is not None:
        payload["instance"] = instance
    if errors is not None:
        payload["errors"] = errors
    response = JSONResponse(
        payload,
        status_code=status_code,
        media_type="application/problem+json",
    )
    response.headers["Content-Type"] = "application/problem+json; charset=utf-8"
    return response


def raise_problem(type_: str, title: str, status_code: int, detail: str, *, errors: list[dict[str, str]] | None = None, headers: dict[str, str] | None = None):
    raise ApiProblem(type_, title, status_code, detail, errors=errors, headers=headers)


def missing(detail="Resource not found"):
    raise HTTPException(status_code=404, detail=detail)


def require_bearer(request: Request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer ") or not authorization[7:].strip():
        raise HTTPException(status_code=401, detail="Bearer authorization is required")


def resource_etag(row) -> str:
    return '"' + hashlib.sha256(json.dumps(list(row), default=str, sort_keys=True).encode()).hexdigest() + '"'


def created(data):
    return data


accounts = APIRouter(prefix="/accounts", tags=["Accounts"])
catalogue = APIRouter(prefix="/catalogue", tags=["Catalogue"])
orders = APIRouter(prefix="/orders", tags=["Orders"])
payments = APIRouter(prefix="/payments", tags=["Payments"])
delivery = APIRouter(prefix="/delivery", tags=["Delivery"])
engagement = APIRouter(prefix="/engagement", tags=["Campus Engagement"])


@accounts.post("/register", status_code=201)
def register(payload: RegisterInput):
    try:
        with transaction() as conn:
            user = conn.execute("""INSERT INTO accounts.users(email,password_hash,role)
                VALUES (%s,%s,%s) RETURNING user_id,email,role,status""",
                (payload.email, pwd_context.hash(payload.password), payload.role)).fetchone()
            conn.execute("INSERT INTO accounts.profiles(user_id,full_name,phone) VALUES (%s,%s,%s)",
                         (user[0], payload.full_name, payload.phone))
        return row_dict(user, ["user_id", "email", "role", "status"])
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(409, "Email is already registered") from exc
        raise


@accounts.post("/login")
def login(payload: LoginInput):
    row = fetch_one("SELECT user_id,email,password_hash,role,status FROM accounts.users WHERE email=%s", (payload.email,))
    if not row or not pwd_context.verify(payload.password, row[2]):
        raise HTTPException(401, "Invalid credentials")
    return row_dict(row, ["user_id", "email", "password_hash", "role", "status"]) | {"password_hash": None}


@accounts.get("/{user_id}/profile")
def get_profile(user_id: int):
    row = fetch_one("""SELECT u.user_id,u.email,u.role,u.status,p.full_name,p.phone
        FROM accounts.users u JOIN accounts.profiles p USING(user_id) WHERE u.user_id=%s""", (user_id,))
    return row_dict(row, ["user_id", "email", "role", "status", "full_name", "phone"]) or missing()


@accounts.put("/{user_id}/profile")
def update_profile(user_id: int, payload: ProfileInput):
    with transaction() as conn:
        row = conn.execute("UPDATE accounts.profiles SET full_name=%s,phone=%s,updated_at=now() WHERE user_id=%s RETURNING user_id,full_name,phone", (payload.full_name, payload.phone, user_id)).fetchone()
    return row_dict(row, ["user_id", "full_name", "phone"]) or missing()


@accounts.post("/{user_id}/locations", status_code=201)
def add_location(user_id: int, payload: LocationInput):
    row = fetch_one("""INSERT INTO accounts.campus_locations(user_id,campus_id,label,building,room,is_default)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING location_id,user_id,campus_id,label,building,room,is_default""",
        (user_id, payload.campus_id, payload.label, payload.building, payload.room, payload.is_default))
    return row_dict(row, ["location_id", "user_id", "campus_id", "label", "building", "room", "is_default"])


@accounts.get("/{user_id}/locations")
def list_locations(user_id: int):
    rows = fetch_all("""SELECT location_id,user_id,campus_id,label,building,room,is_default
        FROM accounts.campus_locations WHERE user_id=%s ORDER BY is_default DESC,location_id""", (user_id,))
    return [row_dict(row, ["location_id", "user_id", "campus_id", "label", "building", "room", "is_default"]) for row in rows]


@accounts.get("/{user_id}/locations/{location_id}")
def get_location(user_id: int, location_id: int):
    row = fetch_one("SELECT location_id,user_id,campus_id,label,building,room,is_default FROM accounts.campus_locations WHERE user_id=%s AND location_id=%s", (user_id, location_id))
    return row_dict(row, ["location_id", "user_id", "campus_id", "label", "building", "room", "is_default"]) or missing()


@catalogue.get("/restaurants")
def list_restaurants(campus_id: int | None = None, search: str | None = None):
    rows = fetch_all("SELECT restaurant_id,owner_user_id,campus_id,name,status FROM catalogue.restaurants WHERE status='ACTIVE' AND (%s::bigint IS NULL OR campus_id=%s) AND (%s::text IS NULL OR name ILIKE '%%'||%s||'%%') ORDER BY name", (campus_id, campus_id, search, search))
    return [row_dict(row, ["restaurant_id", "owner_user_id", "campus_id", "name", "status"]) for row in rows]


@catalogue.post("/restaurants", status_code=201)
def create_restaurant(payload: RestaurantInput):
    row = fetch_one("INSERT INTO catalogue.restaurants(owner_user_id,campus_id,name) VALUES (%s,%s,%s) RETURNING restaurant_id,owner_user_id,campus_id,name,status", (payload.owner_user_id, payload.campus_id, payload.name))
    return row_dict(row, ["restaurant_id", "owner_user_id", "campus_id", "name", "status"])


@catalogue.post("/restaurants/{restaurant_id}/menus", status_code=201)
def create_menu(restaurant_id: int, payload: MenuInput):
    row = fetch_one("INSERT INTO catalogue.menus(restaurant_id,name) VALUES (%s,%s) RETURNING menu_id,restaurant_id,name,status", (restaurant_id, payload.name))
    return row_dict(row, ["menu_id", "restaurant_id", "name", "status"])


@catalogue.get("/restaurants/{restaurant_id}/menu")
def get_menu(restaurant_id: int):
    rows = fetch_all("""SELECT i.item_id,i.menu_id,i.category_id,i.name,i.description,i.price,i.is_available
        FROM catalogue.menu_items i JOIN catalogue.menus m USING(menu_id)
        WHERE m.restaurant_id=%s AND m.status='ACTIVE' ORDER BY i.name""", (restaurant_id,))
    return [row_dict(row, ["item_id", "menu_id", "category_id", "name", "description", "price", "is_available"]) for row in rows]


@catalogue.post("/menus/{menu_id}/items", status_code=201)
def add_item(menu_id: int, payload: ItemInput):
    row = fetch_one("""INSERT INTO catalogue.menu_items(menu_id,category_id,name,description,price,is_available)
        VALUES (%s,%s,%s,%s,%s,%s) RETURNING item_id,menu_id,category_id,name,description,price,is_available""", (menu_id, payload.category_id, payload.name, payload.description, payload.price, payload.is_available))
    return row_dict(row, ["item_id", "menu_id", "category_id", "name", "description", "price", "is_available"])


@catalogue.get("/items/{item_id}/check")
def check_item(item_id: int):
    row = fetch_one("SELECT item_id,name,price,is_available FROM catalogue.menu_items WHERE item_id=%s", (item_id,))
    return row_dict(row, ["item_id", "name", "price", "is_available"]) or missing()


@orders.post("/cart/items", status_code=201)
def add_to_cart(payload: CartItemInput, request: Request):
    require_json_accept(request)
    with transaction() as conn:
        cart = conn.execute("SELECT cart_id FROM orders.carts WHERE user_id=%s AND status='ACTIVE' AND restaurant_id=(SELECT m.restaurant_id FROM catalogue.menus m JOIN catalogue.menu_items i USING(menu_id) WHERE i.item_id=%s) LIMIT 1", (payload.user_id, payload.item_id)).fetchone()
        if not cart:
            restaurant = conn.execute("SELECT m.restaurant_id FROM catalogue.menus m JOIN catalogue.menu_items i USING(menu_id) WHERE i.item_id=%s AND i.is_available", (payload.item_id,)).fetchone()
            if not restaurant:
                raise_problem("item-unavailable", "Item unavailable", 409, "The requested item is unavailable")
            cart = conn.execute("INSERT INTO orders.carts(user_id,restaurant_id) VALUES (%s,%s) RETURNING cart_id", (payload.user_id, restaurant[0])).fetchone()
        row = conn.execute("""INSERT INTO orders.cart_items(cart_id,item_id,quantity) VALUES (%s,%s,%s)
            ON CONFLICT(cart_id,item_id) DO UPDATE SET quantity=orders.cart_items.quantity+EXCLUDED.quantity
            RETURNING cart_item_id,cart_id,item_id,quantity""", (cart[0], payload.item_id, payload.quantity)).fetchone()
    return row_dict(row, ["cart_item_id", "cart_id", "item_id", "quantity"])


@orders.post("", status_code=201)
def place_order(payload: OrderInput, request: Request, response: Response):
    require_json_accept(request)
    if not payload.items:
        raise_problem(
            "empty-cart",
            "Empty cart",
            422,
            "An order must contain at least one item",
            errors=[{"field": "items", "reason": "must contain at least one item"}],
        )
    require_bearer(request)
    idempotency_key = request.headers.get("Idempotency-Key") or payload.idempotency_key
    if not idempotency_key or not idempotency_key.strip():
        raise_problem(
            "validation-failed",
            "Validation failed",
            422,
            "Request validation failed",
            errors=[{"field": "Idempotency-Key", "reason": "is required"}],
        )
    idempotency_key = idempotency_key.strip()
    if len(idempotency_key) > 100:
        raise_problem(
            "validation-failed",
            "Validation failed",
            422,
            "Request validation failed",
            errors=[{"field": "Idempotency-Key", "reason": "must be at most 100 characters"}],
        )
    with transaction() as conn:
        existing = conn.execute(
            """SELECT order_id,user_id,restaurant_id,location_id,fulfilment_type,
                      scheduled_at,status,subtotal,total
               FROM orders.orders WHERE user_id=%s AND idempotency_key=%s""",
            (payload.user_id, idempotency_key),
        ).fetchone()
        if existing:
            order = tuple(existing[:6]) + ("PENDING_PAYMENT",) + tuple(existing[7:])
        else:
            location_id = payload.location_id
            if location_id is None and payload.fulfilment_type == "DELIVERY":
                location = conn.execute(
                    """SELECT location_id FROM accounts.campus_locations
                       WHERE user_id=%s AND (
                           label=%s OR building=%s OR
                           concat_ws(' ', building, room)=%s
                       )
                       ORDER BY is_default DESC, location_id LIMIT 1""",
                    (payload.user_id, payload.address.strip(), payload.address.strip(), payload.address.strip()),
                ).fetchone()
                if not location:
                    raise_problem(
                        "validation-failed",
                        "Validation failed",
                        422,
                        "Request validation failed",
                        errors=[{"field": "address", "reason": "must match a saved campus address"}],
                    )
                location_id = location[0]
            elif location_id is not None:
                location = conn.execute(
                    "SELECT location_id FROM accounts.campus_locations WHERE location_id=%s AND user_id=%s",
                    (location_id, payload.user_id),
                ).fetchone()
                if not location:
                    raise_problem(
                        "validation-failed",
                        "Validation failed",
                        422,
                        "Request validation failed",
                        errors=[{"field": "location_id", "reason": "must reference an address belonging to the user"}],
                    )

            item_rows = []
            total = 0
            restaurant_id = None
            for index, item in enumerate(payload.items):
                row = conn.execute(
                    """SELECT i.name,i.price,i.is_available,m.restaurant_id
                       FROM catalogue.menu_items i JOIN catalogue.menus m USING(menu_id)
                       WHERE i.item_id=%s""",
                    (item.item_id,),
                ).fetchone()
                if not row or not row[2]:
                    raise_problem(
                        "item-unavailable",
                        "Item unavailable",
                        409,
                        "One or more requested items are unavailable",
                        errors=[{"field": f"items[{index}].item_id", "reason": "is unavailable"}],
                    )
                if restaurant_id is not None and restaurant_id != row[3]:
                    raise_problem(
                        "validation-failed",
                        "Validation failed",
                        422,
                        "Request validation failed",
                        errors=[{"field": f"items[{index}].item_id", "reason": "must be from the same restaurant"}],
                    )
                restaurant_id = row[3]
                subtotal = row[1] * item.quantity
                total += subtotal
                item_rows.append((item.item_id, row[0], item.quantity, row[1], subtotal))

            order = conn.execute(
                """INSERT INTO orders.orders(
                       user_id,restaurant_id,location_id,fulfilment_type,scheduled_at,
                       subtotal,total,idempotency_key,status
                   )
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'PENDING_PAYMENT')
                   ON CONFLICT(user_id,idempotency_key)
                   DO UPDATE SET updated_at=orders.orders.updated_at
                   RETURNING order_id,user_id,restaurant_id,location_id,fulfilment_type,
                             scheduled_at,status,subtotal,total""",
                (
                    payload.user_id,
                    restaurant_id,
                    location_id if payload.fulfilment_type == "DELIVERY" else None,
                    payload.fulfilment_type,
                    payload.scheduled_at,
                    total,
                    total,
                    idempotency_key,
                ),
            ).fetchone()
            for item_id, name, quantity, price, subtotal in item_rows:
                conn.execute(
                    """INSERT INTO orders.order_items(
                           order_id,item_id,item_name,quantity,unit_price,subtotal
                       ) VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT DO NOTHING""",
                    (order[0], item_id, name, quantity, price, subtotal),
                )
    order = tuple(order)
    response.headers["Location"] = f"/orders/{order[0]}"
    response.headers["ETag"] = resource_etag(order)
    return row_dict(order, ["order_id", "user_id", "restaurant_id", "location_id", "fulfilment_type", "scheduled_at", "status", "subtotal", "total"])


ORDER_TRANSITIONS = {
    "PENDING_PAYMENT": {"PLACED", "CANCELLED"},
    "PLACED": {"ACCEPTED", "CANCELLED"},
    "ACCEPTED": {"PREPARING", "CANCELLED"},
    "PREPARING": {"READY", "READY_FOR_PICKUP", "OUT_FOR_DELIVERY", "CANCELLED"},
    "READY": {"COMPLETED"},
    "READY_FOR_PICKUP": {"COMPLETED"},
    "OUT_FOR_DELIVERY": {"COMPLETED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def xml_order(payload: dict) -> str:
    root = Element("order")
    for key, value in payload.items():
        node = SubElement(root, key)
        if value is not None:
            node.text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    return tostring(root, encoding="unicode")


def parse_accept_header(value: str | None) -> dict[str, float]:
    if not value or not value.strip():
        return {"*/*": 1.0}
    accepted = {}
    for part in value.split(","):
        media_type, *parameters = part.strip().lower().split(";")
        quality = 1.0
        for parameter in parameters:
            key, separator, raw_value = parameter.strip().partition("=")
            if separator and key == "q":
                try:
                    quality = float(raw_value)
                except ValueError:
                    quality = 0.0
        accepted[media_type.strip()] = quality
    return accepted


def media_quality(accepted: dict[str, float], media_type: str) -> float:
    if media_type in accepted:
        return accepted[media_type]
    family = media_type.split("/", 1)[0] + "/*"
    if family in accepted:
        return accepted[family]
    return accepted.get("*/*", 0)


def negotiate_order_response(request: Request, *, supports_xml: bool) -> str:
    accepted = parse_accept_header(request.headers.get("Accept"))
    json_quality = media_quality(accepted, "application/json")
    xml_quality = media_quality(accepted, "application/xml")
    if supports_xml and xml_quality > json_quality and xml_quality > 0:
        return "xml"
    if json_quality > 0:
        return "json"
    if supports_xml and xml_quality > 0:
        return "xml"
    raise_problem("not-acceptable", "Not acceptable", 406, "Only supported representations are available")


def require_json_accept(request: Request) -> None:
    if negotiate_order_response(request, supports_xml=False) != "json":
        raise_problem("not-acceptable", "Not acceptable", 406, "Only application/json is supported for this operation")


@orders.get("/{order_id}")
def get_order(order_id: int, request: Request, response: Response, user_id: int | None = Query(default=None)):
    representation = negotiate_order_response(request, supports_xml=True)
    require_bearer(request)
    row = fetch_one(
        """SELECT order_id,user_id,restaurant_id,location_id,fulfilment_type,
                  scheduled_at,status,subtotal,total
           FROM orders.orders
           WHERE order_id=%s AND (%s::bigint IS NULL OR user_id=%s)""",
        (order_id, user_id, user_id),
    )
    if not row:
        raise_problem("order-not-found", "Order not found", 404, "The requested order does not exist")
    etag = resource_etag(row)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    if request.headers.get("If-None-Match") == etag:
        response.status_code = 304
        return None
    result = row_dict(row, ["order_id", "user_id", "restaurant_id", "location_id", "fulfilment_type", "scheduled_at", "status", "subtotal", "total"])
    if representation == "xml":
        return Response(
            content=xml_order(result),
            media_type="application/xml; charset=utf-8",
            headers={"ETag": etag, "Cache-Control": response.headers["Cache-Control"]},
        )
    return result

@orders.api_route("/{order_id}", methods=["PUT", "PATCH"])
def update_order(order_id: int, payload: OrderStatusInput, request: Request, response: Response, user_id: int = Query(...)):
    require_json_accept(request)
    require_bearer(request)
    current = fetch_one("SELECT order_id,user_id,restaurant_id,location_id,fulfilment_type,scheduled_at,status,subtotal,total FROM orders.orders WHERE order_id=%s AND user_id=%s", (order_id, user_id))
    if not current:
        raise_problem("order-not-found", "Order not found", 404, "The requested order does not exist")
    current_etag = resource_etag(current)
    if request.headers.get("If-Match") and request.headers["If-Match"] != current_etag:
        raise_problem("precondition-failed", "Precondition failed", 412, "The order has changed")
    if payload.status != current[6] and payload.status not in ORDER_TRANSITIONS.get(current[6], set()):
        raise_problem(
            "illegal-transition",
            "Illegal order transition",
            409,
            f"An order in status {current[6]} cannot transition to {payload.status}",
        )
    row = fetch_one("UPDATE orders.orders SET status=%s,updated_at=now() WHERE order_id=%s AND user_id=%s RETURNING order_id,user_id,restaurant_id,location_id,fulfilment_type,scheduled_at,status,subtotal,total", (payload.status, order_id, user_id))
    if not row:
        raise_problem("order-not-found", "Order not found", 404, "The requested order does not exist")
    response.headers["ETag"] = resource_etag(row)
    return row_dict(row, ["order_id", "user_id", "restaurant_id", "location_id", "fulfilment_type", "scheduled_at", "status", "subtotal", "total"])


@orders.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, request: Request, user_id: int = Query(...)):
    require_json_accept(request)
    require_bearer(request)
    with transaction() as conn:
        row = conn.execute(
            """UPDATE orders.orders SET status='CANCELLED',updated_at=now()
               WHERE order_id=%s AND user_id=%s AND status IN ('PENDING_PAYMENT','PLACED')
               RETURNING order_id""",
            (order_id, user_id),
        ).fetchone()
        if row:
            return Response(status_code=204)
        current = conn.execute(
            "SELECT status FROM orders.orders WHERE order_id=%s AND user_id=%s",
            (order_id, user_id),
        ).fetchone()
        if not current:
            raise_problem("order-not-found", "Order not found", 404, "The requested order does not exist")
        if current[0] != "CANCELLED":
            raise_problem("illegal-transition", "Illegal order transition", 409, "Only pending or placed orders can be cancelled")
    return Response(status_code=204)


@orders.post("/{order_id}/cancel")
def cancel_order(order_id: int, request: Request, user_id: int = Query(...)):
    require_json_accept(request)
    require_bearer(request)
    row = fetch_one("UPDATE orders.orders SET status='CANCELLED',updated_at=now() WHERE order_id=%s AND user_id=%s AND status IN ('PENDING_PAYMENT','PLACED') RETURNING order_id,status", (order_id, user_id))
    if row:
        return row_dict(row, ["order_id", "status"])
    current = fetch_one("SELECT status FROM orders.orders WHERE order_id=%s AND user_id=%s", (order_id, user_id))
    if not current:
        raise_problem("order-not-found", "Order not found", 404, "The requested order does not exist")
    if current[0] == "CANCELLED":
        return row_dict((order_id, "CANCELLED"), ["order_id", "status"])
    raise_problem("illegal-transition", "Illegal order transition", 409, "Only pending or placed orders can be cancelled")


@payments.post("/charge", status_code=201)
def charge(payload: PaymentInput):
    method = fetch_one("SELECT payment_method_id FROM payments.payment_methods WHERE payment_method_id=%s AND user_id=%s AND status='ACTIVE'", (payload.payment_method_id, payload.user_id))
    if not method: raise HTTPException(422, "Invalid payment method")
    reference = hashlib.sha256(f"{payload.user_id}:{payload.order_reference}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:32]
    row = fetch_one("INSERT INTO payments.payments(order_id,user_id,amount,status,provider_reference) VALUES (%s,%s,%s,'CAPTURED',%s) RETURNING payment_id,order_id,amount,status,provider_reference", (payload.order_reference, payload.user_id, payload.amount, reference))
    return {"payment_reference": row[4], "payment_id": row[0], "status": row[3], "amount": row[2]}


@payments.get("/methods")
def list_payment_methods(user_id: int = Query(...)):
    rows = fetch_all("""SELECT payment_method_id,method_type,last4,status
        FROM payments.payment_methods WHERE user_id=%s AND status='ACTIVE'
        ORDER BY payment_method_id""", (user_id,))
    return [row_dict(row, ["payment_method_id", "method_type", "last4", "status"]) for row in rows]


@payments.get("/{payment_reference}")
def payment_status(payment_reference: str):
    row = fetch_one("SELECT payment_id,order_id,amount,status,provider_reference FROM payments.payments WHERE provider_reference=%s", (payment_reference,))
    return row_dict(row, ["payment_id", "order_id", "amount", "status", "provider_reference"]) or missing()


@payments.post("/{payment_reference}/refund", status_code=201)
def refund(payment_reference: str, payload: RefundInput):
    with transaction() as conn:
        payment = conn.execute("SELECT payment_id,amount,status FROM payments.payments WHERE provider_reference=%s FOR UPDATE", (payment_reference,)).fetchone()
        if not payment: missing()
        if payment[2] not in ("CAPTURED", "PARTIALLY_REFUNDED") or payload.amount > payment[1]: raise HTTPException(409, "Refund is not allowed")
        row = conn.execute("INSERT INTO payments.refunds(payment_id,amount,reason,status) VALUES (%s,%s,%s,'SUCCESS') RETURNING refund_id,amount,status", (payment[0], payload.amount, payload.reason)).fetchone()
        conn.execute("UPDATE payments.payments SET status='REFUNDED',updated_at=now() WHERE payment_id=%s", (payment[0],))
    return {"refund_reference": row[0], "amount": row[1], "status": row[2]}


@delivery.post("/fulfilments", status_code=201)
def create_fulfilment(payload: FulfilmentInput):
    if payload.fulfilment_type == "DELIVERY" and payload.location_id is None: raise HTTPException(422, "location_id is required")
    if payload.fulfilment_type == "PICKUP" and payload.pickup_point_id is None: raise HTTPException(422, "pickup_point_id is required")
    row = fetch_one("""INSERT INTO delivery.fulfilments(order_id,fulfilment_type,location_id,pickup_point_id)
        VALUES (%s,%s,%s,%s) RETURNING fulfilment_id,order_id,fulfilment_type,location_id,pickup_point_id,status""", (payload.order_id, payload.fulfilment_type, payload.location_id, payload.pickup_point_id))
    return row_dict(row, ["fulfilment_id", "order_id", "fulfilment_type", "location_id", "pickup_point_id", "status"])


@delivery.post("/fulfilments/{fulfilment_id}/assign", status_code=201)
def assign_delivery(fulfilment_id: int, payload: AssignmentInput):
    row = fetch_one("INSERT INTO delivery.delivery_assignments(fulfilment_id,rider_user_id) VALUES (%s,%s) RETURNING assignment_id,fulfilment_id,rider_user_id,status", (fulfilment_id, payload.rider_user_id))
    return row_dict(row, ["assignment_id", "fulfilment_id", "rider_user_id", "status"])


@delivery.get("/fulfilments/{fulfilment_id}")
def fulfilment_status(fulfilment_id: int):
    row = fetch_one("SELECT fulfilment_id,order_id,fulfilment_type,location_id,pickup_point_id,status,scheduled_for FROM delivery.fulfilments WHERE fulfilment_id=%s", (fulfilment_id,))
    return row_dict(row, ["fulfilment_id", "order_id", "fulfilment_type", "location_id", "pickup_point_id", "status", "scheduled_for"]) or missing()


@engagement.post("/notifications", status_code=201)
def send_notification(payload: NotificationInput):
    row = fetch_one("""INSERT INTO campus_engagement.notifications(user_id,event_type,channel,title,message)
        VALUES (%s,%s,%s,%s,%s) RETURNING notification_id,user_id,event_type,channel,title,message,status""", (payload.user_id, payload.event_type, payload.channel, payload.title, payload.message))
    return row_dict(row, ["notification_id", "user_id", "event_type", "channel", "title", "message", "status"])


@engagement.post("/reviews", status_code=201)
def create_review(payload: ReviewInput):
    if (payload.restaurant_id is None) == (payload.item_id is None): raise HTTPException(422, "Provide exactly one of restaurant_id or item_id")
    table = "restaurant_reviews" if payload.restaurant_id is not None else "item_reviews"
    target = "restaurant_id" if payload.restaurant_id is not None else "item_id"
    row = fetch_one(f"INSERT INTO campus_engagement.{table}(user_id,order_id,{target},rating,comment) VALUES (%s,%s,%s,%s,%s) RETURNING review_id,user_id,order_id,{target},rating,comment", (payload.user_id, payload.order_id, payload.restaurant_id or payload.item_id, payload.rating, payload.comment))
    return row_dict(row, ["review_id", "user_id", "order_id", target, "rating", "comment"])


@engagement.get("/notifications/{user_id}")
def notifications(user_id: int):
    rows = fetch_all("SELECT notification_id,user_id,event_type,channel,title,message,status,created_at FROM campus_engagement.notifications WHERE user_id=%s ORDER BY created_at DESC", (user_id,))
    return [row_dict(row, ["notification_id", "user_id", "event_type", "channel", "title", "message", "status", "created_at"]) for row in rows]


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


def cors_allowed_origins() -> list[str]:
    configured = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://localhost:5500,http://127.0.0.1:5500",
    )
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


app = FastAPI(title="CampusEats Services", version="1.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "If-Match", "If-None-Match", "Idempotency-Key", "X-HTTP-Method-Override", "X-Client-ID"],
)

RATE_LIMIT = 60
RATE_WINDOW_SECONDS = 60
rate_buckets: dict[str, tuple[float, int]] = {}


def validation_field(location: tuple) -> str:
    parts = [str(part) for part in location if part not in {"body", "query", "path", "header"}]
    if not parts:
        return "address" if not location else "request"
    field = parts[0]
    for part in parts[1:]:
        if part.isdigit():
            field += f"[{part}]"
        else:
            field += f".{part}"
    return field.replace(".quantity", ".qty")


def validation_reason(error: dict, field: str) -> str:
    if field.endswith(".qty"):
        return "must be an integer >= 1"
    if field == "address":
        return "must be a non-empty address"
    reason_map = {
        "int_type": "must be an integer",
        "int_parsing": "must be an integer",
        "greater_than": "must be greater than zero",
        "string_type": "must be a string",
        "string_too_short": "must not be empty",
        "missing": "is required",
        "json_invalid": "must be valid JSON",
    }
    return reason_map.get(error.get("type"), error.get("msg", "is invalid"))


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    validation_errors = []
    for error in exc.errors():
        field = validation_field(tuple(error.get("loc", ())))
        validation_errors.append({"field": field, "reason": validation_reason(error, field)})

    if request.url.path == "/orders":
        try:
            body = json.loads(await request.body())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return problem(
                "validation-failed",
                "Malformed JSON",
                400,
                "The request body must contain valid JSON",
                instance=request_instance(request),
                errors=[{"field": "request", "reason": "must be valid JSON"}],
            )
        if isinstance(body, dict) and not str(body.get("address") or "").strip():
            if not any(error["field"] == "address" for error in validation_errors):
                validation_errors.append({"field": "address", "reason": "must be a non-empty address"})
    status_code = 400 if any(error.get("type") == "json_invalid" for error in exc.errors()) else 422
    return problem(
        "validation-failed",
        "Malformed JSON" if status_code == 400 else "Validation failed",
        status_code,
        "The request body must contain valid JSON" if status_code == 400 else "Request validation failed",
        instance=request_instance(request),
        errors=validation_errors,
    )


@app.exception_handler(ApiProblem)
async def api_problem_exception_handler(request: Request, exc: ApiProblem):
    headers = dict(exc.headers)
    if exc.status_code in {429, 503}:
        headers.setdefault("Retry-After", "3")
    response = problem(
        exc.type,
        exc.title,
        exc.status_code,
        exc.detail,
        instance=request_instance(request),
        errors=exc.errors,
    )
    response.headers.update(headers)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    status = exc.status_code
    title_map = {
        400: ("validation-failed", "Bad request"),
        401: ("unauthorized", "Unauthorized"),
        402: ("payment-declined", "Payment declined"),
        404: ("order-not-found" if request.url.path.startswith("/orders/") else "not-found", "Resource not found"),
        405: ("method-not-allowed", "Method not allowed"),
        406: ("not-acceptable", "Not acceptable"),
        409: ("illegal-transition", "Conflict"),
        422: ("validation-failed", "Validation failed"),
        429: ("rate-limited", "Rate limit exceeded"),
        412: ("precondition-failed", "Precondition failed"),
        500: ("internal-error", "Internal server error"),
        503: ("service-unavailable", "Service unavailable"),
    }
    problem_type, title = title_map.get(status, ("internal-error", "Request failed"))
    if status == 503:
        detail = "A required service is temporarily unavailable"
    elif status >= 500:
        detail = "An unexpected error occurred"
    else:
        detail = str(exc.detail)
    headers = dict(exc.headers or {})
    if status in {429, 503}:
        headers.setdefault("Retry-After", "3")
    errors = [{"field": "request", "reason": detail}] if status == 422 else None
    response = problem(problem_type, title, status, detail, instance=request_instance(request), errors=errors)
    response.headers.update(headers)
    return response


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 405:
        type_, title, detail = "method-not-allowed", "Method not allowed", "The HTTP method is not supported"
    elif exc.status_code == 404 and request.url.path.startswith("/orders/"):
        type_, title, detail = "order-not-found", "Order not found", "The requested order does not exist"
    else:
        type_, title, detail = "not-found", "Resource not found", "The requested resource does not exist"
    return problem(type_, title, exc.status_code, detail, instance=request_instance(request))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled request failure for %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    if isinstance(exc, (TimeoutError, psycopg.OperationalError, psycopg.errors.QueryCanceled)):
        response = problem(
            "service-unavailable",
            "Service unavailable",
            503,
            "A required service is temporarily unavailable",
            instance=request_instance(request),
        )
        response.headers["Retry-After"] = "3"
        return response
    return problem(
        "internal-error",
        "Internal server error",
        500,
        "An unexpected error occurred",
        instance=request_instance(request),
    )


@app.middleware("http")
async def http_policy(request: Request, call_next):
    method = request.headers.get("X-HTTP-Method-Override", request.method).upper()
    if request.method == "POST" and method in {"PUT", "PATCH", "DELETE"}:
        request.scope["method"] = method

    client_id = request.headers.get("X-Client-ID") or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    started, count = rate_buckets.get(client_id, (now, 0))
    if now - started >= RATE_WINDOW_SECONDS:
        started, count = now, 0
    if count >= RATE_LIMIT:
        response = problem(
            "rate-limited",
            "Rate limit exceeded",
            429,
            "Rate limit exceeded",
            instance=request_instance(request),
        )
        response.headers["Retry-After"] = str(max(1, int(RATE_WINDOW_SECONDS - (now - started))))
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT)
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    rate_buckets[client_id] = (started, count + 1)

    accepted = parse_accept_header(request.headers.get("Accept"))
    path = getattr(getattr(request, "url", None), "path", "/")
    is_orders_path = path == "/orders" or path.startswith("/orders/")
    if request.method != "OPTIONS" and not is_orders_path and media_quality(accepted, "application/json") <= 0:
        response = problem("not-acceptable", "Not acceptable", 406, "Only application/json is supported", instance=request_instance(request))
    elif request.method == "OPTIONS":
        response = Response(status_code=204, headers={"Allow": "GET, POST, PUT, PATCH, DELETE, OPTIONS"})
        origin = request.headers.get("Origin")
        allowed_origins = cors_allowed_origins()
        if origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Accept, Authorization, Content-Type, If-Match, If-None-Match, Idempotency-Key, X-HTTP-Method-Override, X-Client-ID"
    else:
        response = await call_next(request)

    response.headers.setdefault("X-RateLimit-Limit", str(RATE_LIMIT))
    response.headers.setdefault("X-RateLimit-Remaining", str(max(0, RATE_LIMIT - count - 1)))
    response.headers["X-Content-Type-Options"] = "nosniff"
    content_type = response.headers.get("Content-Type", "application/json")
    if "charset=" not in content_type.lower():
        response.headers["Content-Type"] = f"{content_type}; charset=utf-8"
    if os.getenv("ENVIRONMENT", "development") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
from api.services.accounts.router import router as accounts_router
from api.services.catalogue.router import router as catalogue_router
from api.services.orders.router import router as orders_router
from api.services.payments.router import router as payments_router
from api.services.delivery.router import router as delivery_router
from api.services.engagement.router import router as engagement_router

for service_router in (
    accounts_router,
    catalogue_router,
    orders_router,
    payments_router,
    delivery_router,
    engagement_router,
):
    app.include_router(service_router)


@app.get("/health", tags=["Platform"])
def health():
    return {"status": "ok"}


@app.get("/health/database", tags=["Platform"])
def database_health():
    try:
        check_connection()
    except Exception as exc:
        logger.error(
            "Database health check failed",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ok", "database": "connected"}