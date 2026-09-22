from fastapi import APIRouter

from api.main import assign_delivery, create_fulfilment, fulfilment_status

router = APIRouter(prefix="/delivery", tags=["Delivery"])
router.add_api_route("/fulfilments", create_fulfilment, methods=["POST"], status_code=201)
router.add_api_route("/fulfilments/{fulfilment_id}/assign", assign_delivery, methods=["POST"], status_code=201)
router.add_api_route("/fulfilments/{fulfilment_id}", fulfilment_status, methods=["GET"])