from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_staff_user
from app.api.routes.customer_orders import build_order_out
from app.db.session import get_session
from app.models.enums import CustomerOrderStatus
from app.models.order import CustomerOrder
from app.models.product import InventoryItem
from app.models.user import User
from app.schemas.customer_order import AdminCustomerOrderUpdate, CustomerOrderOut
from app.services.audit_service import record as audit_record

router = APIRouter()


@router.get("", response_model=list[CustomerOrderOut])
async def list_customer_orders(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    status_filter: CustomerOrderStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CustomerOrderOut]:
    stmt = (
        select(CustomerOrder)
        .options(selectinload(CustomerOrder.lines))
        .order_by(CustomerOrder.id.desc())
        .offset(skip)
        .limit(limit)
    )
    if status_filter is not None:
        stmt = stmt.where(CustomerOrder.status == status_filter)
    result = await session.execute(stmt)
    orders = list(result.scalars().unique().all())
    return [await build_order_out(session, o) for o in orders]


@router.get("/{order_id}", response_model=CustomerOrderOut)
async def get_customer_order(
    order_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
) -> CustomerOrderOut:
    stmt = (
        select(CustomerOrder)
        .options(selectinload(CustomerOrder.lines))
        .where(CustomerOrder.id == order_id)
    )
    result = await session.execute(stmt)
    o = result.scalar_one_or_none()
    if o is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return await build_order_out(session, o)


@router.patch("/{order_id}", response_model=CustomerOrderOut)
async def update_customer_order_status(
    order_id: int,
    body: AdminCustomerOrderUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> CustomerOrderOut:
    stmt = (
        select(CustomerOrder)
        .options(selectinload(CustomerOrder.lines))
        .where(CustomerOrder.id == order_id)
    )
    result = await session.execute(stmt)
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    old = order.status
    new = body.status
    if old == new:
        return await build_order_out(session, order)

    if old == CustomerOrderStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change a cancelled order",
        )

    if new == CustomerOrderStatus.CANCELLED:
        if old != CustomerOrderStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only paid orders can be cancelled (inventory restore)",
            )
        await _restore_inventory(session, order)
    elif new == CustomerOrderStatus.FULFILLED:
        if old != CustomerOrderStatus.PAID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only fulfill from paid status",
            )
    elif new == CustomerOrderStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid transition to paid",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported status transition {old!s} -> {new!s}",
        )

    order.status = new
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="customer_order.status_update",
        entity_type="customer_order",
        entity_id=str(order.id),
        payload={"from": old.value, "to": new.value},
    )
    await session.commit()
    await session.refresh(order)

    stmt = (
        select(CustomerOrder)
        .options(selectinload(CustomerOrder.lines))
        .where(CustomerOrder.id == order_id)
    )
    result = await session.execute(stmt)
    refreshed = result.scalar_one()
    return await build_order_out(session, refreshed)


async def _restore_inventory(session: AsyncSession, order: CustomerOrder) -> None:
    for line in order.lines:
        r = await session.execute(
            select(InventoryItem)
            .where(InventoryItem.product_id == line.product_id)
            .with_for_update(),
        )
        inv = r.scalar_one_or_none()
        if inv is None:
            inv = InventoryItem(product_id=line.product_id, quantity=Decimal("0"))
            session.add(inv)
            await session.flush()
        inv.quantity = (inv.quantity + line.quantity).quantize(Decimal("0.0001"))
