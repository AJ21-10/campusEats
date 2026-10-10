from fastapi import APIRouter

from api.main import add_to_cart, cancel_order, delete_order, get_order, place_order, update_order

router = APIRouter(prefix="/orders", tags=["Orders"])
router.add_api_route("/cart/items", add_to_cart, methods=["POST"], status_code=201)
router.add_api_route("", place_order, methods=["POST"], status_code=201)
router.add_api_route("/{order_id}", get_order, methods=["GET"])
router.add_api_route("/{order_id}", update_order, methods=["PUT", "PATCH"])
router.add_api_route("/{order_id}", delete_order, methods=["DELETE"], status_code=204)
router.add_api_route("/{order_id}/cancel", cancel_order, methods=["POST"])