def problem(type_: str, title: str, status: int, detail: str):
    return {
        "type": type_,
        "title": title,
        "status": status,
        "detail": detail,
    }, status
