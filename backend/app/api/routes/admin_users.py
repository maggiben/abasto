from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_staff_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.user import UserPublic
from app.services.audit_service import record as audit_record

router = APIRouter()


@router.post("/{user_id}/promote", response_model=UserPublic)
async def promote_user_to_staff(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if user.is_staff:
        return user
    user.is_staff = True
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="user.promote_to_staff",
        entity_type="user",
        entity_id=str(user.id),
        payload={"promoted_email": user.email},
    )
    await session.commit()
    await session.refresh(user)
    return user
