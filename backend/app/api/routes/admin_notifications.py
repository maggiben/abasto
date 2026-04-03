from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_staff_user
from app.db.session import get_session
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationCreate, NotificationOut
from app.services.audit_service import record as audit_record

router = APIRouter()


@router.post("", response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
async def create_notification(
    body: NotificationCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> Notification:
    n = Notification(
        user_id=body.user_id,
        type=body.type,
        title=body.title,
        body=body.body,
        payload=body.payload,
    )
    session.add(n)
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="notification.create",
        entity_type="notification",
        entity_id=None,
        payload={"target_user_id": body.user_id, "type": str(body.type)},
    )
    await session.commit()
    await session.refresh(n)
    return n
