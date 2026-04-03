import csv
import io
import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_staff_user
from app.db.session import get_session
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut

router = APIRouter()


@router.get("/export")
async def export_audit_logs_csv(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    entity_type: str | None = None,
    action: str | None = None,
    actor_user_id: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = Query(default=10_000, ge=1, le=100_000),
) -> Response:
    stmt = select(AuditLog).order_by(AuditLog.id.asc())
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if created_from is not None:
        stmt = stmt.where(AuditLog.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(AuditLog.created_at <= created_to)
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["id", "actor_user_id", "action", "entity_type", "entity_id", "payload_json", "created_at"],
    )
    for r in rows:
        w.writerow(
            [
                r.id,
                r.actor_user_id if r.actor_user_id is not None else "",
                r.action,
                r.entity_type,
                r.entity_id if r.entity_id is not None else "",
                json.dumps(r.payload) if r.payload is not None else "",
                r.created_at.astimezone(timezone.utc).isoformat(),
            ],
        )
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="audit-logs-{ts}.csv"'},
    )


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    entity_type: str | None = None,
    action: str | None = None,
    actor_user_id: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).offset(skip).limit(limit)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if created_from is not None:
        stmt = stmt.where(AuditLog.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(AuditLog.created_at <= created_to)
    result = await session.execute(stmt)
    return list(result.scalars().all())
