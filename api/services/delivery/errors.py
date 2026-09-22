from fastapi import HTTPException


def unavailable(detail="Delivery service unavailable"):
    raise HTTPException(status_code=422, detail=detail)