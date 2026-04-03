from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_staff_user
from app.db.session import get_session
from app.models.product import InventoryItem
from app.models.user import User
from app.models.vendor_order import VendorOrder, VendorOrderLine
from app.schemas.vendor_order import (
    VendorOrderCreate,
    VendorOrderOut,
    VendorOrderUpdate,
    VendorReceiveRequest,
)
from app.services.audit_service import record as audit_record

router = APIRouter()


@router.get("", response_model=list[VendorOrderOut])
async def list_vendor_orders(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[VendorOrder]:
    stmt = (
        select(VendorOrder)
        .options(selectinload(VendorOrder.lines))
        .order_by(VendorOrder.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


@router.post("", response_model=VendorOrderOut, status_code=status.HTTP_201_CREATED)
async def create_vendor_order(
    body: VendorOrderCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> VendorOrder:
    vo = VendorOrder(
        supplier_name=body.supplier_name,
        notes=body.notes,
        expected_at=body.expected_at,
    )
    session.add(vo)
    await session.flush()
    for ln in body.lines:
        session.add(
            VendorOrderLine(
                vendor_order_id=vo.id,
                product_id=ln.product_id,
                quantity_ordered=ln.quantity_ordered,
                unit_cost=ln.unit_cost,
            ),
        )
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="vendor_order.create",
        entity_type="vendor_order",
        entity_id=str(vo.id),
        payload={"supplier": body.supplier_name},
    )
    await session.commit()
    stmt = (
        select(VendorOrder)
        .options(selectinload(VendorOrder.lines))
        .where(VendorOrder.id == vo.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


@router.get("/{vendor_order_id}", response_model=VendorOrderOut)
async def get_vendor_order(
    vendor_order_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
) -> VendorOrder:
    stmt = (
        select(VendorOrder)
        .options(selectinload(VendorOrder.lines))
        .where(VendorOrder.id == vendor_order_id)
    )
    result = await session.execute(stmt)
    vo = result.scalar_one_or_none()
    if vo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor order not found")
    return vo


@router.patch("/{vendor_order_id}", response_model=VendorOrderOut)
async def update_vendor_order(
    vendor_order_id: int,
    body: VendorOrderUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> VendorOrder:
    stmt = select(VendorOrder).where(VendorOrder.id == vendor_order_id)
    result = await session.execute(stmt)
    vo = result.scalar_one_or_none()
    if vo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor order not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(vo, k, v)
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="vendor_order.update",
        entity_type="vendor_order",
        entity_id=str(vo.id),
        payload=data,
    )
    await session.commit()
    stmt = (
        select(VendorOrder)
        .options(selectinload(VendorOrder.lines))
        .where(VendorOrder.id == vendor_order_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


@router.post("/{vendor_order_id}/receive", response_model=VendorOrderOut)
async def receive_vendor_stock(
    vendor_order_id: int,
    body: VendorReceiveRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> VendorOrder:
    stmt = (
        select(VendorOrderLine)
        .where(
            VendorOrderLine.id == body.line_id,
            VendorOrderLine.vendor_order_id == vendor_order_id,
        )
    )
    result = await session.execute(stmt)
    line = result.scalar_one_or_none()
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor order line not found",
        )

    new_received = (line.quantity_received + body.add_quantity).quantize(Decimal("0.0001"))
    if new_received > line.quantity_ordered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Received quantity cannot exceed ordered quantity",
        )
    line.quantity_received = new_received

    inv_r = await session.execute(
        select(InventoryItem)
        .where(InventoryItem.product_id == line.product_id)
        .with_for_update(),
    )
    inv = inv_r.scalar_one_or_none()
    if inv is None:
        inv = InventoryItem(product_id=line.product_id, quantity=Decimal("0"))
        session.add(inv)
        await session.flush()
    inv.quantity = (inv.quantity + body.add_quantity).quantize(Decimal("0.0001"))

    await audit_record(
        session,
        actor_user_id=staff.id,
        action="vendor_order.receive",
        entity_type="vendor_order_line",
        entity_id=str(line.id),
        payload={"add_quantity": str(body.add_quantity)},
    )
    await session.commit()

    stmt = (
        select(VendorOrder)
        .options(selectinload(VendorOrder.lines))
        .where(VendorOrder.id == vendor_order_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()
