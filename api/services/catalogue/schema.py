import asyncio
from collections import defaultdict
from decimal import Decimal
from typing import Any, TypeVar

import strawberry
from pydantic import BaseModel, ValidationError
from strawberry.dataloader import DataLoader
from strawberry.types import Info

from api.db import fetch_all, fetch_one
from api.schemas import (
    ItemInput as ItemInputModel,
    MenuInput as MenuInputModel,
    RestaurantInput as RestaurantInputModel,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _restaurant(row: tuple) -> "Restaurant":
    return Restaurant(
        restaurant_id=row[0],
        owner_user_id=row[1],
        campus_id=row[2],
        name=row[3],
        status=row[4],
    )


def _menu_item(row: tuple) -> "MenuItem":
    return MenuItem(
        item_id=row[0],
        menu_id=row[1],
        category_id=row[2],
        name=row[3],
        description=row[4],
        price=row[5],
        is_available=row[6],
    )


@strawberry.type
class MenuItem:
    item_id: int
    menu_id: int
    category_id: int | None
    name: str
    description: str | None
    price: Decimal
    is_available: bool


@strawberry.type
class Restaurant:
    restaurant_id: int
    owner_user_id: int
    campus_id: int
    name: str
    status: str

    @strawberry.field
    async def menu_items(self, info: Info) -> list[MenuItem]:
        loader: DataLoader[int, list[MenuItem]] = info.context["menu_items_loader"]
        return await loader.load(self.restaurant_id)


@strawberry.type
class Menu:
    menu_id: int
    restaurant_id: int
    name: str
    status: str


@strawberry.input
class RestaurantInput:
    owner_user_id: int
    campus_id: int
    name: str


@strawberry.input
class MenuInput:
    name: str


@strawberry.input
class MenuItemInput:
    category_id: int | None = None
    name: str
    description: str | None = None
    price: Decimal
    is_available: bool = True


@strawberry.type
class Query:
    @strawberry.field
    def restaurants(
        self, campus_id: int | None = None, search: str | None = None
    ) -> list[Restaurant]:
        rows = fetch_all(
            """SELECT restaurant_id,owner_user_id,campus_id,name,status
            FROM catalogue.restaurants
            WHERE status='ACTIVE'
                AND (%s::bigint IS NULL OR campus_id=%s)
                AND (%s::text IS NULL OR name ILIKE '%%'||%s||'%%')
            ORDER BY name""",
            (campus_id, campus_id, search, search),
        )
        return [_restaurant(row) for row in rows]

    @strawberry.field
    def restaurant(self, restaurant_id: int) -> Restaurant | None:
        row = fetch_one(
            """SELECT restaurant_id,owner_user_id,campus_id,name,status
            FROM catalogue.restaurants
            WHERE restaurant_id=%s AND status='ACTIVE'""",
            (restaurant_id,),
        )
        return _restaurant(row) if row else None

    @strawberry.field
    def menu_item(self, item_id: int) -> MenuItem | None:
        row = fetch_one(
            """SELECT item_id,menu_id,category_id,name,description,price,is_available
            FROM catalogue.menu_items WHERE item_id=%s""",
            (item_id,),
        )
        return _menu_item(row) if row else None


def _validated(model: type[ModelT], payload: dict[str, Any]) -> ModelT:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_restaurant(self, input: RestaurantInput) -> Restaurant:
        payload = _validated(RestaurantInputModel, strawberry.asdict(input))
        row = fetch_one(
            """INSERT INTO catalogue.restaurants(owner_user_id,campus_id,name)
            VALUES (%s,%s,%s)
            RETURNING restaurant_id,owner_user_id,campus_id,name,status""",
            (payload.owner_user_id, payload.campus_id, payload.name),
        )
        return _restaurant(row)

    @strawberry.mutation
    def create_menu(self, restaurant_id: int, input: MenuInput) -> Menu:
        payload = _validated(MenuInputModel, strawberry.asdict(input))
        row = fetch_one(
            """INSERT INTO catalogue.menus(restaurant_id,name)
            VALUES (%s,%s) RETURNING menu_id,restaurant_id,name,status""",
            (restaurant_id, payload.name),
        )
        return Menu(
            menu_id=row[0],
            restaurant_id=row[1],
            name=row[2],
            status=row[3],
        )

    @strawberry.mutation
    def add_menu_item(self, menu_id: int, input: MenuItemInput) -> MenuItem:
        payload = _validated(ItemInputModel, strawberry.asdict(input))
        row = fetch_one(
            """INSERT INTO catalogue.menu_items
                (menu_id,category_id,name,description,price,is_available)
            VALUES (%s,%s,%s,%s,%s,%s)
            RETURNING item_id,menu_id,category_id,name,description,price,is_available""",
            (
                menu_id,
                payload.category_id,
                payload.name,
                payload.description,
                payload.price,
                payload.is_available,
            ),
        )
        return _menu_item(row)


async def _load_menu_items(restaurant_ids: list[int]) -> list[list[MenuItem]]:
    rows = await asyncio.to_thread(
        fetch_all,
        """SELECT m.restaurant_id,i.item_id,i.menu_id,i.category_id,i.name,
            i.description,i.price,i.is_available
        FROM catalogue.menus m
        JOIN catalogue.menu_items i USING(menu_id)
        WHERE m.restaurant_id=ANY(%s) AND m.status='ACTIVE'
        ORDER BY i.name""",
        (restaurant_ids,),
    )
    by_restaurant: dict[int, list[MenuItem]] = defaultdict(list)
    for row in rows:
        restaurant_id, *item_values = row
        by_restaurant[restaurant_id].append(_menu_item(tuple(item_values)))
    return [by_restaurant[restaurant_id] for restaurant_id in restaurant_ids]


async def get_context() -> dict[str, DataLoader[int, list[MenuItem]]]:
    return {"menu_items_loader": DataLoader(load_fn=_load_menu_items)}


schema = strawberry.Schema(query=Query, mutation=Mutation)
