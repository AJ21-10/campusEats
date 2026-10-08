from fastapi import APIRouter

from api.main import add_location, get_location, get_profile, list_locations, login, register, update_profile

router = APIRouter(prefix="/accounts", tags=["Accounts"])
router.add_api_route("/register", register, methods=["POST"], status_code=201)
router.add_api_route("/login", login, methods=["POST"])
router.add_api_route("/{user_id}/profile", get_profile, methods=["GET"])
router.add_api_route("/{user_id}/profile", update_profile, methods=["PUT"])
router.add_api_route("/{user_id}/locations", add_location, methods=["POST"], status_code=201)
router.add_api_route("/{user_id}/locations", list_locations, methods=["GET"])
router.add_api_route("/{user_id}/locations/{location_id}", get_location, methods=["GET"])