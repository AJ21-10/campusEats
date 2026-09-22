from fastapi import HTTPException


def declined(detail="Payment declined"):
    raise HTTPException(status_code=422, detail=detail)