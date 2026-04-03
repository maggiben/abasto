from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    action: str
    entity_type: str
    entity_id: str | None
    payload: dict[str, Any] | None
    created_at: datetime
