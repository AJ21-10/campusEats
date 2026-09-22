from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib

from fastapi import APIRouter, FastAPI, HTTPException, Query, status
from passlib.context import CryptContext

from api.db import check_connection, fetch_all, fetch_one, transaction
from api.schemas import (
    AssignmentInput, CartItemInput, FulfilmentInput, ItemInput, LocationInput,
    MenuInput, NotificationInput, OrderInput, PaymentInput, ProfileInput,
    RefundInput, RegisterInput, RestaurantInput, ReviewInput, row_dict,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def missing(detail="Resource not found"):
    raise HTTPException(status_code=404, detail=detail)


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
def login(email: str, password: str):
    row = fetch_one("SELECT user_id,email,password_hash,role,status FROM accounts.users WHERE email=%s", (email,))
    if not row or not pwd_context.verify(password, row[2]):
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


@accounts.get("/{user_id}/locations/{location_id}")
def get_location(user_id: int, location_id: int):
    row = fetch_one("SELECT location_id,user_id,campus_id,label,building,room,is_default FROM accounts.campus_locations WHERE user_id=%s AND location_id=%s", (user_id, location_id))
    return row_dict(row, ["location_id", "user_id", "campus_id", "label", "building", "room", "is_default"]) or missing()


@catalogue.get("/restaurants")
def list_restaurants(campus_id: int | None = None, search: str | None = None):
    rows = fetch_all("SELECT restaurant_id,owner_user_id,campus_id,name,status FROM catalogue.restaurants WHERE status='ACTIVE' AND (%s IS NULL OR campus_id=%s) AND (%s IS NULL OR name ILIKE '%%'||%s||'%%') ORDER BY name", (campus_id, campus_id, search, search))
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
def add_to_cart(payload: CartItemInput):
    with transaction() as conn:
        cart = conn.execute("SELECT cart_id FROM orders.carts WHERE user_id=%s AND status='ACTIVE' AND restaurant_id=(SELECT m.restaurant_id FROM catalogue.menus m JOIN catalogue.menu_items i USING(menu_id) WHERE i.item_id=%s) LIMIT 1", (payload.user_id, payload.item_id)).fetchone()
        if not cart:
            restaurant = conn.execute("SELECT m.restaurant_id FROM catalogue.menus m JOIN catalogue.menu_items i USING(menu_id) WHERE i.item_id=%s AND i.is_available", (payload.item_id,)).fetchone()
            if not restaurant: raise HTTPException(409, "Item is unavailable")
            cart = conn.execute("INSERT INTO orders.carts(user_id,restaurant_id) VALUES (%s,%s) RETURNING cart_id", (payload.user_id, restaurant[0])).fetchone()
        row = conn.execute("""INSERT INTO orders.cart_items(cart_id,item_id,quantity) VALUES (%s,%s,%s)
            ON CONFLICT(cart_id,item_id) DO UPDATE SET quantity=orders.cart_items.quantity+EXCLUDED.quantity
            RETURNING cart_item_id,cart_id,item_id,quantity""", (cart[0], payload.item_id, payload.quantity)).fetchone()
    return row_dict(row, ["cart_item_id", "cart_id", "item_id", "quantity"])


@orders.post("", status_code=201)
def place_order(payload: OrderInput):
    with transaction() as conn:
        item_rows = []
        total = 0
        restaurant_id = None
        for item in payload.items:
            row = conn.execute("""SELECT i.name,i.price,i.is_available,m.restaurant_id FROM catalogue.menu_items i JOIN catalogue.menus m USING(menu_id) WHERE i.item_id=%s""", (item.item_id,)).fetchone()
            if not row or not row[2]: raise HTTPException(409, f"Item {item.item_id} is unavailable")
            if restaurant_id is not None and restaurant_id != row[3]: raise HTTPException(422, "All items must be from one restaurant")
            restaurant_id = row[3]; subtotal = row[1] * item.quantity; total += subtotal
            item_rows.append((item.item_id, row[0], item.quantity, row[1], subtotal))
        if payload.fulfilment_type == "DELIVERY" and payload.location_id is None: raise HTTPException(422, "location_id is required for delivery")
        order = conn.execute("""INSERT INTO orders.orders(user_id,restaurant_id,location_id,fulfilment_type,scheduled_at,subtotal,total,idempotency_key,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'PENDING_PAYMENT') ON CONFLICT(user_id,idempotency_key) DO UPDATE SET updated_at=now()
            RETURNING order_id,user_id,restaurant_id,location_id,fulfilment_type,scheduled_at,status,subtotal,total""", (payload.user_id, restaurant_id, payload.location_id if payload.fulfilment_type == "DELIVERY" else None, payload.fulfilment_type, payload.scheduled_at, total, total, payload.idempotency_key)).fetchone()
        for item_id, name, quantity, price, subtotal in item_rows:
            conn.execute("INSERT INTO orders.order_items(order_id,item_id,item_name,quantity,unit_price,subtotal) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (order[0], item_id, name, quantity, price, subtotal))
    return row_dict(order, ["order_id", "user_id", "restaurant_id", "location_id", "fulfilment_type", "scheduled_at", "status", "subtotal", "total"])


@orders.get("/{order_id}")
def get_order(order_id: int, user_id: int = Query(...)):
    row = fetch_one("SELECT order_id,user_id,restaurant_id,location_id,fulfilment_type,scheduled_at,status,subtotal,total FROM orders.orders WHERE order_id=%s AND user_id=%s", (order_id, user_id))
    return row_dict(row, ["order_id", "user_id", "restaurant_id", "location_id", "fulfilment_type", "scheduled_at", "status", "subtotal", "total"]) or missing()


@orders.post("/{order_id}/cancel")
def cancel_order(order_id: int, user_id: int = Query(...)):
    row = fetch_one("UPDATE orders.orders SET status='CANCELLED',updated_at=now() WHERE order_id=%s AND user_id=%s AND status IN ('PENDING_PAYMENT','PLACED') RETURNING order_id,status", (order_id, user_id))
    return row_dict(row, ["order_id", "status"]) or missing("Order cannot be cancelled")


@payments.post("/charge", status_code=201)
def charge(payload: PaymentInput):
    method = fetch_one("SELECT payment_method_id FROM payments.payment_methods WHERE payment_method_id=%s AND user_id=%s AND status='ACTIVE'", (payload.payment_method_id, payload.user_id))
    if not method: raise HTTPException(422, "Invalid payment method")
    reference = hashlib.sha256(f"{payload.user_id}:{payload.order_reference}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()[:32]
    row = fetch_one("INSERT INTO payments.payments(order_id,user_id,amount,status,provider_reference) VALUES (%s,%s,%s,'CAPTURED',%s) RETURNING payment_id,order_id,amount,status,provider_reference", (payload.order_reference, payload.user_id, payload.amount, reference))
    return {"payment_reference": row[4], "payment_id": row[0], "status": row[3], "amount": row[2]}


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


app = FastAPI(title="CampusEats Services", version="1.0.0", lifespan=lifespan)
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
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ok", "database": "connected"}