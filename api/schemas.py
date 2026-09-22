from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProfileInput(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    phone: str | None = Field(default=None, max_length=30)


class RegisterInput(ProfileInput):
    email: str
    password: str = Field(min_length=8)
    role: Literal["STUDENT", "VENDOR", "DELIVERY_STAFF", "ADMIN"] = "STUDENT"


class LocationInput(BaseModel):
    campus_id: int
    label: str
    building: str
    room: str | None = None
    is_default: bool = False


class RestaurantInput(BaseModel):
    owner_user_id: int
    campus_id: int
    name: str = Field(min_length=1, max_length=150)


class MenuInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ItemInput(BaseModel):
    category_id: int | None = None
    name: str
    description: str | None = None
    price: Decimal = Field(ge=0)
    is_available: bool = True


class CartItemInput(BaseModel):
    user_id: int
    item_id: int
    quantity: int = Field(gt=0)


class OrderItemInput(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)


class OrderInput(BaseModel):
    user_id: int
    items: list[OrderItemInput] = Field(min_length=1)
    location_id: int | None = None
    payment_method_id: int
    fulfilment_type: Literal["PICKUP", "DELIVERY"]
    scheduled_at: datetime | None = None
    idempotency_key: str = Field(min_length=1, max_length=100)


class PaymentInput(BaseModel):
    user_id: int
    amount: Decimal = Field(gt=0)
    payment_method_id: int
    order_reference: int


class RefundInput(BaseModel):
    amount: Decimal = Field(gt=0)
    reason: str | None = None


class FulfilmentInput(BaseModel):
    order_id: int
    fulfilment_type: Literal["PICKUP", "DELIVERY"]
    location_id: int | None = None
    pickup_point_id: int | None = None


class AssignmentInput(BaseModel):
    rider_user_id: int


class NotificationInput(BaseModel):
    user_id: int
    event_type: str
    message: str
    channel: Literal["IN_APP", "EMAIL", "SMS"] = "IN_APP"
    title: str = "CampusEats notification"


class ReviewInput(BaseModel):
    user_id: int
    order_id: int
    restaurant_id: int | None = None
    item_id: int | None = None
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


def row_dict(row: Any, columns: list[str]) -> dict[str, Any] | None:
    return dict(zip(columns, row)) if row else None