from sqlalchemy import or_


def ilike_search(
    search: str | None,
    *columns,
):
    if not search:
        return None

    return or_(*[column.ilike(f"%{search}%") for column in columns])
