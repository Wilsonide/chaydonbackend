from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PaginationMeta


def build_page(
    *,
    items: list,
    total: int,
    page: int,
    limit: int,
):
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=max(1, ceil(total / limit)),
        ),
    )
