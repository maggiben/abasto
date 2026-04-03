from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_staff_user
from app.db.session import get_session
from app.models.enums import NotificationType
from app.models.notification import Notification
from app.models.product import InventoryItem, Product
from app.models.user import User
from app.schemas.inventory import (
    ExpiringStockAlert,
    InventoryAdjust,
    InventoryUpsert,
    LowStockAlert,
    LowStockNotifyResult,
)
from app.schemas.product import InventoryPublic
from app.services.audit_service import record as audit_record

router = APIRouter()


@router.get("/products/{product_id}", response_model=InventoryPublic)
async def get_inventory(
    product_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
) -> InventoryItem:
    await _require_product(session, product_id)
    stmt = select(InventoryItem).where(InventoryItem.product_id == product_id)
    result = await session.execute(stmt)
    inv = result.scalar_one_or_none()
    if inv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory row not found; create the product first",
        )
    return inv


@router.put("/products/{product_id}", response_model=InventoryPublic)
async def upsert_inventory(
    product_id: int,
    body: InventoryUpsert,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> InventoryItem:
    await _require_product(session, product_id)
    stmt = select(InventoryItem).where(InventoryItem.product_id == product_id)
    result = await session.execute(stmt)
    inv = result.scalar_one_or_none()
    if inv is None:
        inv = InventoryItem(
            product_id=product_id,
            quantity=body.quantity,
            low_stock_threshold=body.low_stock_threshold,
        )
        session.add(inv)
    else:
        inv.quantity = body.quantity
        inv.low_stock_threshold = body.low_stock_threshold
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="inventory.upsert",
        entity_type="product",
        entity_id=str(product_id),
        payload=body.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(inv)
    return inv


@router.post("/products/{product_id}/adjust", response_model=InventoryPublic)
async def adjust_inventory(
    product_id: int,
    body: InventoryAdjust,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> InventoryItem:
    await _require_product(session, product_id)
    stmt = select(InventoryItem).where(InventoryItem.product_id == product_id)
    result = await session.execute(stmt)
    inv = result.scalar_one_or_none()
    if inv is None:
        inv = InventoryItem(product_id=product_id, quantity=Decimal("0"))
        session.add(inv)
        await session.flush()
    new_qty = inv.quantity + body.delta
    if new_qty < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adjustment would make quantity negative",
        )
    inv.quantity = new_qty
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="inventory.adjust",
        entity_type="product",
        entity_id=str(product_id),
        payload={"delta": str(body.delta), "quantity": str(inv.quantity)},
    )
    await session.commit()
    await session.refresh(inv)
    return inv


async def _require_product(session: AsyncSession, product_id: int) -> None:
    r = await session.execute(select(Product.id).where(Product.id == product_id))
    if r.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")


async def _query_low_stock_alerts(session: AsyncSession) -> list[LowStockAlert]:
    stmt = (
        select(Product, InventoryItem)
        .join(InventoryItem, InventoryItem.product_id == Product.id)
        .where(
            Product.is_active.is_(True),
            InventoryItem.low_stock_threshold.is_not(None),
            InventoryItem.quantity <= InventoryItem.low_stock_threshold,
        )
        .order_by(Product.name.asc())
    )
    result = await session.execute(stmt)
    out: list[LowStockAlert] = []
    for p, inv in result.all():
        out.append(
            LowStockAlert(
                product_id=p.id,
                name=p.name,
                barcode=p.barcode,
                quantity=inv.quantity,
                low_stock_threshold=inv.low_stock_threshold,
            ),
        )
    return out


@router.get("/alerts/low-stock", response_model=list[LowStockAlert])
async def list_low_stock_alerts(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
) -> list[LowStockAlert]:
    return await _query_low_stock_alerts(session)


@router.post("/alerts/notify-low-stock", response_model=LowStockNotifyResult)
async def notify_low_stock(
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> LowStockNotifyResult:
    alerts = await _query_low_stock_alerts(session)
    if not alerts:
        return LowStockNotifyResult(
            staff_users=0,
            notifications_created=0,
            low_stock_products=0,
        )
    ur = await session.execute(
        select(User).where(User.is_staff.is_(True), User.is_active.is_(True)),
    )
    staff_users = list(ur.scalars().all())
    names = ", ".join(a.name for a in alerts[:25])
    if len(alerts) > 25:
        names += f", … (+{len(alerts) - 25} more)"
    title = f"Low stock: {len(alerts)} product(s)"
    body = names or "Thresholds reached."
    payload = {
        "product_ids": [a.product_id for a in alerts],
        "count": len(alerts),
    }
    for u in staff_users:
        session.add(
            Notification(
                user_id=u.id,
                type=NotificationType.LOW_STOCK,
                title=title,
                body=body,
                payload=payload,
            ),
        )
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="inventory.notify_low_stock",
        entity_type="notification",
        entity_id=None,
        payload={"low_stock_products": len(alerts), "staff_notified": len(staff_users)},
    )
    await session.commit()
    return LowStockNotifyResult(
        staff_users=len(staff_users),
        notifications_created=len(staff_users),
        low_stock_products=len(alerts),
    )


@router.get("/alerts/expiring", response_model=list[ExpiringStockAlert])
async def list_expiring_stock(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    within_days: int = Query(default=30, ge=1, le=365),
) -> list[ExpiringStockAlert]:
    today = date.today()
    until = today + timedelta(days=within_days)
    stmt = (
        select(Product, InventoryItem)
        .join(InventoryItem, InventoryItem.product_id == Product.id)
        .where(
            Product.is_active.is_(True),
            Product.expiration_date.is_not(None),
            Product.expiration_date <= until,
        )
        .order_by(Product.expiration_date.asc(), Product.name.asc())
    )
    result = await session.execute(stmt)
    out: list[ExpiringStockAlert] = []
    for p, inv in result.all():
        out.append(
            ExpiringStockAlert(
                product_id=p.id,
                name=p.name,
                barcode=p.barcode,
                expiration_date=p.expiration_date,
                quantity=inv.quantity,
            ),
        )
    return out
