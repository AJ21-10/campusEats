from fastapi import HTTPException


def conflict(detail="Order state conflict"):
    raise HTTPException(status_code=409, detail=detail)