from fastapi import APIRouter

from api.main import create_review, notifications, send_notification

router = APIRouter(prefix="/engagement", tags=["Campus Engagement"])
router.add_api_route("/notifications", send_notification, methods=["POST"], status_code=201)
router.add_api_route("/reviews", create_review, methods=["POST"], status_code=201)
router.add_api_route("/notifications/{user_id}", notifications, methods=["GET"])