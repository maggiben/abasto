from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    title: str
    body: str
    payload: dict[str, Any] | None
    read_at: datetime | None
    created_at: datetime


class NotificationCreate(BaseModel):
    """Staff: notify a specific user (MVP — no broadcast row)."""

    user_id: int = Field(ge=1)
    type: NotificationType
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)
    payload: dict[str, Any] | None = None
