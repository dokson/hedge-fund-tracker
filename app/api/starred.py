"""
Server-backed favorites under /api/me/starred.

Endpoints:
- GET    /api/me/starred[?type=stock|fund|quarter]  — list, optional filter
- POST   /api/me/starred                              — add (idempotent)
- DELETE /api/me/starred/{type}/{item_id}             — remove

`item_id` validation per type happens here (not at the DB layer) so we can
return 400 with a useful message instead of a generic constraint error.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Final

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.auth.dependencies import current_active_verified_user
from app.db.models import StarredItem, StarredItemType, User
from app.db.session import AsyncSessionLocal
from app.patterns import FUND_NAME_RE, QUARTER_RE, TICKER_RE

router = APIRouter(prefix="/api/me/starred", tags=["me", "favorites"])

# Per-type item_id validators. Tickers and quarter codes are tightly bounded;
# fund denomination is free text but excludes HTML-meaningful characters as a
# defence-in-depth — React already escapes on render, but we'd rather not rely
# on a single layer of mitigation if a future template/email renderer drops it.
_VALIDATORS: Final[dict[StarredItemType, re.Pattern[str]]] = {
    StarredItemType.STOCK: TICKER_RE,
    StarredItemType.QUARTER: QUARTER_RE,
    StarredItemType.FUND: FUND_NAME_RE,
}


def _validate_item_id(item_type: StarredItemType, item_id: str) -> None:
    """
    Reject malformed item_ids early. Raises 400 — never a DB-level error.
    """
    pattern = _VALIDATORS[item_type]
    if not pattern.fullmatch(item_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid item_id {item_id!r} for type {item_type.value!r}",
        )


class StarredItemPayload(BaseModel):
    """
    POST body. `note` reserved for future UI; persisted but no API yet.
    """

    item_type: StarredItemType
    item_id: str = Field(..., min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=500)


class StarredItemOut(BaseModel):
    """
    Wire format.
    """

    id: uuid.UUID
    item_type: StarredItemType
    item_id: str
    note: str | None
    starred_at: datetime


def _to_out(row: StarredItem) -> StarredItemOut:
    """
    ORM row → wire DTO.
    """
    return StarredItemOut(
        id=row.id,
        item_type=row.item_type,
        item_id=row.item_id,
        note=row.note,
        starred_at=row.starred_at,
    )


@router.get("", response_model=list[StarredItemOut])
async def list_starred(
    type: StarredItemType | None = None,  # noqa: A002 — query name reads natural
    user: User = Depends(current_active_verified_user),
) -> list[StarredItemOut]:
    """
    List the user's stars, optionally filtered by item_type. Newest first.
    """
    stmt = select(StarredItem).where(StarredItem.user_id == user.id)
    if type is not None:
        stmt = stmt.where(StarredItem.item_type == type)
    stmt = stmt.order_by(StarredItem.starred_at.desc())

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(stmt)).scalars().all()
        return [_to_out(r) for r in rows]


@router.post(
    "",
    response_model=StarredItemOut,
    status_code=status.HTTP_201_CREATED,
)
async def star_item(
    payload: StarredItemPayload,
    user: User = Depends(current_active_verified_user),
) -> StarredItemOut:
    """
    Star an item. Idempotent: re-starring the same (type, id) returns the
    existing row instead of erroring.
    """
    _validate_item_id(payload.item_type, payload.item_id)

    async with AsyncSessionLocal() as session:
        # ON CONFLICT DO NOTHING — idempotent insert.
        stmt = (
            insert(StarredItem)
            .values(
                user_id=user.id,
                item_type=payload.item_type.value,
                item_id=payload.item_id,
                note=payload.note,
            )
            .on_conflict_do_nothing(constraint="starred_items_unique")
        )
        await session.execute(stmt)

        # Read back the (possibly pre-existing) row.
        existing = (
            await session.execute(
                select(StarredItem).where(
                    StarredItem.user_id == user.id,
                    StarredItem.item_type == payload.item_type,
                    StarredItem.item_id == payload.item_id,
                )
            )
        ).scalar_one()
        await session.commit()
        return _to_out(existing)


@router.delete(
    "/{item_type}/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unstar_item(
    item_type: StarredItemType,
    item_id: str,
    user: User = Depends(current_active_verified_user),
) -> None:
    """
    Unstar an item. Idempotent: returns 204 even if it was already gone
    (anti-IDOR — never reveal whether someone else has it).
    """
    _validate_item_id(item_type, item_id)

    async with AsyncSessionLocal() as session:
        row = (
            await session.execute(
                select(StarredItem).where(
                    StarredItem.user_id == user.id,
                    StarredItem.item_type == item_type,
                    StarredItem.item_id == item_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            await session.delete(row)
            await session.commit()
