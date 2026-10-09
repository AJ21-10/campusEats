from fastapi import HTTPException


def not_found(detail="Catalogue resource not found"):
    raise HTTPException(status_code=404, detail=detail)