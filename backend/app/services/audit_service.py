from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def record(
    session: AsyncSession,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    payload: dict | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        ),
    )
