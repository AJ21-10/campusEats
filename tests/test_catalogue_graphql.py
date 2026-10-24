from decimal import Decimal

from fastapi.testclient import TestClient

import api.services.catalogue.schema as catalogue_schema
from api.main import app, rate_buckets


def setup_function():
    rate_buckets.clear()


def test_restaurants_query_returns_camel_case_graphql_fields(monkeypatch):
    monkeypatch.setattr(
        catalogue_schema,
        "fetch_all",
        lambda query, params: [(7, 3, 2, "Campus Cafe", "ACTIVE")],
    )

    response = TestClient(app).post(
        "/catalogue/graphql",
        json={
            "query": """
                query {
                    restaurants(search: "Cafe") {
                        restaurantId
                        campusId
                        name
                        status
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "restaurants": [
                {
                    "restaurantId": 7,
                    "campusId": 2,
                    "name": "Campus Cafe",
                    "status": "ACTIVE",
                }
            ]
        }
    }


def test_restaurant_query_loads_menu_items(monkeypatch):
    def fetch_one(_query, _params):
        return (7, 3, 2, "Campus Cafe", "ACTIVE")

    def fetch_all(_query, params):
        assert params == ([7],)
        return [(7, 12, 4, None, "Tea", "Fresh tea", Decimal("2.50"), True)]

    monkeypatch.setattr(catalogue_schema, "fetch_one", fetch_one)
    monkeypatch.setattr(catalogue_schema, "fetch_all", fetch_all)

    response = TestClient(app).post(
        "/catalogue/graphql",
        json={
            "query": """
                query {
                    restaurant(restaurantId: 7) {
                        name
                        menuItems {
                            itemId
                            name
                            price
                            isAvailable
                        }
                    }
                }
            """
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]["restaurant"]
    assert data["name"] == "Campus Cafe"
    assert data["menuItems"] == [
        {
            "itemId": 12,
            "name": "Tea",
            "price": "2.50",
            "isAvailable": True,
        }
    ]


def test_create_restaurant_mutation_validates_and_returns_created_value(monkeypatch):
    def fetch_one(query, params):
        assert "INSERT INTO catalogue.restaurants" in query
        assert params == (3, 2, "Campus Cafe")
        return (7, 3, 2, "Campus Cafe", "ACTIVE")

    monkeypatch.setattr(catalogue_schema, "fetch_one", fetch_one)
    response = TestClient(app).post(
        "/catalogue/graphql",
        json={
            "query": """
                mutation CreateRestaurant($input: RestaurantInput!) {
                    createRestaurant(input: $input) {
                        restaurantId
                        name
                        status
                    }
                }
            """,
            "variables": {
                "input": {
                    "ownerUserId": 3,
                    "campusId": 2,
                    "name": "Campus Cafe",
                }
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["createRestaurant"] == {
        "restaurantId": 7,
        "name": "Campus Cafe",
        "status": "ACTIVE",
    }


def test_catalogue_rest_endpoints_are_removed():
    response = TestClient(app).get("/catalogue/restaurants")

    assert response.status_code == 404
