from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_staff_user
from app.config import get_settings
from app.db.session import get_session
from app.models.enums import CustomerOrderStatus
from app.models.order import CustomerOrder, CustomerOrderLine, Sale, SaleLine
from app.models.product import InventoryItem
from app.models.user import User
from app.schemas.sale import ResetSalesOut, SaleDetail, SaleLineDetail, SaleSummary
from app.services.audit_service import record as audit_record

router = APIRouter()


@router.post("/reset-all", response_model=ResetSalesOut)
async def reset_all_sales(
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> ResetSalesOut:
    """Remove every POS sale and web customer order, restoring stock from deducted lines."""
    settings = get_settings()
    if not settings.allow_reset_sales:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Reset sales is disabled on this server. Set ALLOW_RESET_SALES=true in the API "
                "environment if you need this for testing."
            ),
        )

    pos_count_row = await session.execute(select(func.count()).select_from(Sale))
    pos_removed = int(pos_count_row.scalar_one() or 0)

    sale_lines = await session.execute(select(SaleLine.product_id, SaleLine.quantity))
    for product_id, qty in sale_lines.all():
        await _add_quantity_to_inventory(session, int(product_id), Decimal(str(qty)))

    web_lines = await session.execute(
        select(CustomerOrderLine.product_id, CustomerOrderLine.quantity)
        .join(CustomerOrder, CustomerOrder.id == CustomerOrderLine.order_id)
        .where(
            CustomerOrder.status.in_(
                (CustomerOrderStatus.PAID, CustomerOrderStatus.FULFILLED),
            ),
        ),
    )
    web_removed_row = await session.execute(select(func.count()).select_from(CustomerOrder))
    web_removed = int(web_removed_row.scalar_one() or 0)

    for product_id, qty in web_lines.all():
        await _add_quantity_to_inventory(session, int(product_id), Decimal(str(qty)))

    await session.execute(delete(Sale))
    await session.execute(delete(CustomerOrder))

    await audit_record(
        session,
        actor_user_id=staff.id,
        action="admin.sales_reset_all",
        entity_type="sales",
        entity_id=None,
        payload={"pos_tickets_removed": pos_removed, "web_orders_removed": web_removed},
    )
    await session.commit()
    return ResetSalesOut(pos_tickets_removed=pos_removed, web_orders_removed=web_removed)


async def _add_quantity_to_inventory(session: AsyncSession, product_id: int, quantity: Decimal) -> None:
    r = await session.execute(
        select(InventoryItem)
        .where(InventoryItem.product_id == product_id)
        .with_for_update(),
    )
    inv = r.scalar_one_or_none()
    if inv is None:
        inv = InventoryItem(product_id=product_id, quantity=Decimal("0"))
        session.add(inv)
        await session.flush()
    inv.quantity = (inv.quantity + quantity).quantize(Decimal("0.0001"))


@router.get("", response_model=list[SaleSummary])
async def list_sales(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Sale]:
    stmt = (
        select(Sale)
        .order_by(Sale.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{sale_id}", response_model=SaleDetail)
async def get_sale(
    sale_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
) -> SaleDetail:
    stmt = (
        select(Sale)
        .options(selectinload(Sale.lines))
        .where(Sale.id == sale_id)
    )
    result = await session.execute(stmt)
    s = result.scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    line_details = [
        SaleLineDetail(
            product_id=sl.product_id,
            product_name=sl.product_name,
            quantity=sl.quantity,
            unit_price=sl.unit_price,
            line_total=sl.line_total,
        )
        for sl in s.lines
    ]
    return SaleDetail(
        id=s.id,
        created_at=s.created_at,
        cashier_user_id=s.cashier_user_id,
        subtotal=s.subtotal,
        tax_total=s.tax_total,
        total=s.total,
        lines=line_details,
    )
