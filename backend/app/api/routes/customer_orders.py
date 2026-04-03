from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_user_optional
from app.config import get_settings
from app.db.session import get_session
from app.models.enums import CustomerOrderStatus
from app.models.order import CustomerOrder, CustomerOrderLine
from app.models.product import Product
from app.models.user import User
from app.schemas.customer_order import CustomerOrderCreate, CustomerOrderLineOut, CustomerOrderOut
from app.schemas.sale import ReceiptLineOut
from app.services.audit_service import record as audit_record
from app.services.checkout_common import apply_inventory_deduction, prepare_checkout

router = APIRouter()


@router.post("", response_model=CustomerOrderOut, status_code=status.HTTP_201_CREATED)
async def create_customer_order(
    body: CustomerOrderCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> CustomerOrderOut:
    if user is None and body.guest_email is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="guest_email is required for guest checkout",
        )
    settings = get_settings()
    rate = (
        body.tax_rate_percent
        if body.tax_rate_percent is not None
        else settings.default_tax_rate_percent
    )
    prepared = await prepare_checkout(session, body.lines, rate)

    order = CustomerOrder(
        user_id=user.id if user else None,
        guest_email=str(body.guest_email) if body.guest_email else None,
        status=CustomerOrderStatus.PAID,
        subtotal=prepared.subtotal,
        tax_total=prepared.tax_total,
        total=prepared.total,
    )
    session.add(order)
    await session.flush()

    for rl in prepared.receipt_lines:
        session.add(
            CustomerOrderLine(
                order_id=order.id,
                product_id=rl.product_id,
                quantity=rl.quantity,
                unit_price=rl.unit_price,
                line_total=rl.line_total,
            ),
        )

    apply_inventory_deduction(prepared)
    await audit_record(
        session,
        actor_user_id=user.id if user else None,
        action="customer_order.create",
        entity_type="customer_order",
        entity_id=str(order.id),
        payload={
            "total": str(prepared.total),
            "guest_email": order.guest_email,
            "lines": len(prepared.receipt_lines),
        },
    )
    await session.commit()
    await session.refresh(order)

    return _to_order_out(order, prepared.rate, prepared.receipt_lines)


@router.get("/me", response_model=list[CustomerOrderOut])
async def list_my_orders(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    skip: int = 0,
    limit: int = 50,
) -> list[CustomerOrderOut]:
    stmt = (
        select(CustomerOrder)
        .options(selectinload(CustomerOrder.lines))
        .where(CustomerOrder.user_id == user.id)
        .order_by(CustomerOrder.id.desc())
        .offset(skip)
        .limit(min(limit, 100))
    )
    result = await session.execute(stmt)
    orders = list(result.scalars().unique().all())
    return [await build_order_out(session, o) for o in orders]


@router.get("/track/{tracking_token}", response_model=CustomerOrderOut)
async def track_order(
    tracking_token: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CustomerOrderOut:
    stmt = (
        select(CustomerOrder)
        .options(selectinload(CustomerOrder.lines))
        .where(CustomerOrder.tracking_token == tracking_token)
    )
    result = await session.execute(stmt)
    o = result.scalar_one_or_none()
    if o is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return await build_order_out(session, o)


def _infer_tax_rate(order: CustomerOrder) -> Decimal:
    if order.subtotal == 0:
        return Decimal("0")
    return (order.tax_total / order.subtotal * Decimal(100)).quantize(Decimal("0.0001"))


async def build_order_out(session: AsyncSession, order: CustomerOrder) -> CustomerOrderOut:
    rate = _infer_tax_rate(order)
    lines_out: list[CustomerOrderLineOut] = []
    for line in order.lines:
        pr = await session.execute(select(Product).where(Product.id == line.product_id))
        p = pr.scalar_one()
        lines_out.append(
            CustomerOrderLineOut(
                product_id=line.product_id,
                product_name=p.name,
                quantity=line.quantity,
                unit_price=line.unit_price,
                line_total=line.line_total,
            ),
        )
    return CustomerOrderOut(
        id=order.id,
        tracking_token=order.tracking_token,
        status=order.status,
        subtotal=order.subtotal,
        tax_total=order.tax_total,
        total=order.total,
        tax_rate_percent=rate,
        guest_email=order.guest_email,
        created_at=order.created_at,
        lines=lines_out,
    )


def _to_order_out(
    order: CustomerOrder,
    rate: Decimal,
    receipt_lines: list[ReceiptLineOut],
) -> CustomerOrderOut:
    lines_out = [
        CustomerOrderLineOut(
            product_id=rl.product_id,
            product_name=rl.product_name,
            quantity=rl.quantity,
            unit_price=rl.unit_price,
            line_total=rl.line_total,
        )
        for rl in receipt_lines
    ]
    return CustomerOrderOut(
        id=order.id,
        tracking_token=order.tracking_token,
        status=order.status,
        subtotal=order.subtotal,
        tax_total=order.tax_total,
        total=order.total,
        tax_rate_percent=rate,
        guest_email=order.guest_email,
        created_at=order.created_at,
        lines=lines_out,
    )
