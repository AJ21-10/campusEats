from fastapi import APIRouter

from api.main import add_item, check_item, create_menu, create_restaurant, get_menu, list_restaurants

router = APIRouter(prefix="/catalogue", tags=["Catalogue"])
router.add_api_route("/restaurants", list_restaurants, methods=["GET"])
router.add_api_route("/restaurants", create_restaurant, methods=["POST"], status_code=201)
router.add_api_route("/restaurants/{restaurant_id}/menus", create_menu, methods=["POST"], status_code=201)
router.add_api_route("/restaurants/{restaurant_id}/menu", get_menu, methods=["GET"])
router.add_api_route("/menus/{menu_id}/items", add_item, methods=["POST"], status_code=201)
router.add_api_route("/items/{item_id}/check", check_item, methods=["GET"])