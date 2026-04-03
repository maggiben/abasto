from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationOut

router = APIRouter()


@router.get("", response_model=list[NotificationOut])
async def list_my_notifications(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    unread_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Notification]:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.id.desc())
        .offset(skip)
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.patch("/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_read(
    notification_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> Notification:
    stmt = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == user.id,
    )
    result = await session.execute(stmt)
    n = result.scalar_one_or_none()
    if n is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    from datetime import datetime, timezone

    n.read_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(n)
    return n
