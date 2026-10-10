from fastapi import HTTPException


def invalid_review(detail="Invalid review"):
    raise HTTPException(status_code=422, detail=detail)