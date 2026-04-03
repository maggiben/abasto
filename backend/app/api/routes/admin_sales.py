from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_staff_user
from app.db.session import get_session
from app.models.order import Sale
from app.models.user import User
from app.schemas.sale import SaleDetail, SaleLineDetail, SaleSummary

router = APIRouter()


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
