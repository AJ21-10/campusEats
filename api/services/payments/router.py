from fastapi import APIRouter

from api.main import charge, payment_status, refund

router = APIRouter(prefix="/payments", tags=["Payments"])
router.add_api_route("/charge", charge, methods=["POST"], status_code=201)
router.add_api_route("/{payment_reference}", payment_status, methods=["GET"])
router.add_api_route("/{payment_reference}/refund", refund, methods=["POST"], status_code=201)