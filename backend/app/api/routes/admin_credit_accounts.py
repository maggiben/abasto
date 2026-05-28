"""Cuentas corrientes: clients who buy on a running tab.

Unpaid items are priced live from the current product price; the total debt is
computed on read. Partial payments settle individual items (e.g. pay the wine,
keep the sugar), snapshotting the price charged at settlement time.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_staff_user
from app.config import get_settings
from app.db.session import get_session
from app.models.credit_account import (
    CreditAccountClient,
    CreditAccountItem,
    CreditAccountPayment,
)
from app.models.product import Product
from app.models.user import User
from app.schemas.credit_account import (
    CreditClientCreate,
    CreditClientDetail,
    CreditClientSummary,
    CreditClientUpdate,
    CreditItemCreate,
    CreditItemOut,
    CreditPaymentCreate,
    CreditPaymentOut,
    CreditSettledItemOut,
)
from app.services.audit_service import record as audit_record
from app.services.receipt_printer import try_print_credit_payment
from app.services.receipt_printer_config import load_resolved_receipt_layout

router = APIRouter()

CENTS = Decimal("0.0001")


async def compute_client_debt(session: AsyncSession, client_id: int) -> Decimal:
    """Live total of unpaid items at current product prices."""
    r = await session.execute(
        select(
            func.coalesce(func.sum(CreditAccountItem.quantity * Product.price), Decimal("0")),
        )
        .join(Product, Product.id == CreditAccountItem.product_id)
        .where(
            CreditAccountItem.client_id == client_id,
            CreditAccountItem.settled_at.is_(None),
        ),
    )
    return Decimal(str(r.scalar_one() or 0)).quantize(CENTS)


async def _get_client(session: AsyncSession, client_id: int) -> CreditAccountClient:
    r = await session.execute(
        select(CreditAccountClient).where(CreditAccountClient.id == client_id),
    )
    client = r.scalar_one_or_none()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit account client not found",
        )
    return client


async def _build_detail(session: AsyncSession, client: CreditAccountClient) -> CreditClientDetail:
    # Unpaid items, priced live against the current product price.
    items_stmt = (
        select(CreditAccountItem, Product)
        .join(Product, Product.id == CreditAccountItem.product_id)
        .where(
            CreditAccountItem.client_id == client.id,
            CreditAccountItem.settled_at.is_(None),
        )
        .order_by(CreditAccountItem.created_at.asc(), CreditAccountItem.id.asc())
    )
    items_rows = (await session.execute(items_stmt)).all()
    items: list[CreditItemOut] = []
    total_debt = Decimal("0")
    for item, product in items_rows:
        unit_price = product.price
        line_total = (unit_price * item.quantity).quantize(CENTS)
        total_debt += line_total
        items.append(
            CreditItemOut(
                id=item.id,
                product_id=item.product_id,
                product_name=product.name,
                barcode=product.barcode,
                quantity=item.quantity,
                unit_price=unit_price,
                line_total=line_total,
                note=item.note,
                created_at=item.created_at,
            ),
        )
    total_debt = total_debt.quantize(CENTS)

    # Payment history with the items each one settled.
    payments_stmt = (
        select(CreditAccountPayment)
        .where(CreditAccountPayment.client_id == client.id)
        .order_by(CreditAccountPayment.created_at.desc(), CreditAccountPayment.id.desc())
    )
    payments_rows = list((await session.execute(payments_stmt)).scalars().all())
    payments: list[CreditPaymentOut] = []
    if payments_rows:
        settled_stmt = (
            select(CreditAccountItem, Product)
            .join(Product, Product.id == CreditAccountItem.product_id)
            .where(
                CreditAccountItem.payment_id.in_([p.id for p in payments_rows]),
            )
            .order_by(CreditAccountItem.id.asc())
        )
        settled_rows = (await session.execute(settled_stmt)).all()
        by_payment: dict[int, list[CreditSettledItemOut]] = {}
        for item, product in settled_rows:
            by_payment.setdefault(item.payment_id, []).append(
                CreditSettledItemOut(
                    id=item.id,
                    product_id=item.product_id,
                    product_name=product.name,
                    quantity=item.quantity,
                    unit_price=item.settled_unit_price or Decimal("0"),
                    line_total=item.settled_line_total or Decimal("0"),
                ),
            )
        for p in payments_rows:
            payments.append(
                CreditPaymentOut(
                    id=p.id,
                    amount=p.amount,
                    note=p.note,
                    created_by_user_id=p.created_by_user_id,
                    created_at=p.created_at,
                    items=by_payment.get(p.id, []),
                ),
            )

    return CreditClientDetail(
        id=client.id,
        name=client.name,
        phone=client.phone,
        notes=client.notes,
        is_active=client.is_active,
        created_at=client.created_at,
        updated_at=client.updated_at,
        total_debt=total_debt,
        items=items,
        payments=payments,
    )


@router.get("", response_model=list[CreditClientSummary])
async def list_clients(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    q: str | None = Query(default=None, description="Filter by name or phone (substring)."),
    include_inactive: bool = Query(default=False),
) -> list[CreditClientSummary]:
    debt_sub = (
        select(
            CreditAccountItem.client_id.label("client_id"),
            func.coalesce(
                func.sum(CreditAccountItem.quantity * Product.price), Decimal("0")
            ).label("debt"),
            func.count(CreditAccountItem.id).label("item_count"),
        )
        .join(Product, Product.id == CreditAccountItem.product_id)
        .where(CreditAccountItem.settled_at.is_(None))
        .group_by(CreditAccountItem.client_id)
        .subquery()
    )
    stmt = (
        select(
            CreditAccountClient,
            func.coalesce(debt_sub.c.debt, Decimal("0")),
            func.coalesce(debt_sub.c.item_count, 0),
        )
        .outerjoin(debt_sub, debt_sub.c.client_id == CreditAccountClient.id)
        .order_by(CreditAccountClient.name.asc())
    )
    if not include_inactive:
        stmt = stmt.where(CreditAccountClient.is_active.is_(True))
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            CreditAccountClient.name.ilike(term) | CreditAccountClient.phone.ilike(term),
        )
    rows = (await session.execute(stmt)).all()
    return [
        CreditClientSummary(
            id=client.id,
            name=client.name,
            phone=client.phone,
            notes=client.notes,
            is_active=client.is_active,
            created_at=client.created_at,
            updated_at=client.updated_at,
            total_debt=Decimal(str(debt)).quantize(CENTS),
            unpaid_item_count=int(item_count),
        )
        for client, debt, item_count in rows
    ]


@router.post("", response_model=CreditClientDetail, status_code=status.HTTP_201_CREATED)
async def create_client(
    body: CreditClientCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> CreditClientDetail:
    client = CreditAccountClient(
        name=body.name.strip(),
        phone=body.phone,
        notes=body.notes,
    )
    session.add(client)
    await session.flush()
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="credit_account.client_create",
        entity_type="credit_account_client",
        entity_id=str(client.id),
        payload={"name": client.name},
    )
    await session.commit()
    await session.refresh(client)
    return await _build_detail(session, client)


@router.get("/{client_id}", response_model=CreditClientDetail)
async def get_client(
    client_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
) -> CreditClientDetail:
    client = await _get_client(session, client_id)
    return await _build_detail(session, client)


@router.patch("/{client_id}", response_model=CreditClientDetail)
async def update_client(
    client_id: int,
    body: CreditClientUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> CreditClientDetail:
    client = await _get_client(session, client_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    for k, v in data.items():
        setattr(client, k, v)
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="credit_account.client_update",
        entity_type="credit_account_client",
        entity_id=str(client.id),
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    await session.commit()
    await session.refresh(client)
    return await _build_detail(session, client)


@router.delete("/{client_id}", response_model=CreditClientDetail)
async def deactivate_client(
    client_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> CreditClientDetail:
    client = await _get_client(session, client_id)
    client.is_active = False
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="credit_account.client_deactivate",
        entity_type="credit_account_client",
        entity_id=str(client.id),
        payload=None,
    )
    await session.commit()
    await session.refresh(client)
    return await _build_detail(session, client)


@router.post("/{client_id}/items", response_model=CreditClientDetail, status_code=status.HTTP_201_CREATED)
async def add_item(
    client_id: int,
    body: CreditItemCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> CreditClientDetail:
    client = await _get_client(session, client_id)
    pr = await session.execute(select(Product).where(Product.id == body.product_id))
    product = pr.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product {body.product_id} not found",
        )
    if not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product {body.product_id} is not active",
        )
    item = CreditAccountItem(
        client_id=client.id,
        product_id=product.id,
        quantity=body.quantity,
        note=body.note,
    )
    session.add(item)
    await session.flush()
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="credit_account.item_add",
        entity_type="credit_account_item",
        entity_id=str(item.id),
        payload={
            "client_id": client.id,
            "product_id": product.id,
            "quantity": str(body.quantity),
        },
    )
    await session.commit()
    await session.refresh(client)
    return await _build_detail(session, client)


@router.delete("/{client_id}/items/{item_id}", response_model=CreditClientDetail)
async def delete_item(
    client_id: int,
    item_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> CreditClientDetail:
    client = await _get_client(session, client_id)
    r = await session.execute(
        select(CreditAccountItem).where(
            CreditAccountItem.id == item_id,
            CreditAccountItem.client_id == client.id,
        ),
    )
    item = r.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if item.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an item that has already been paid",
        )
    await session.delete(item)
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="credit_account.item_delete",
        entity_type="credit_account_item",
        entity_id=str(item_id),
        payload={"client_id": client.id},
    )
    await session.commit()
    await session.refresh(client)
    return await _build_detail(session, client)


@router.post("/{client_id}/payments", response_model=CreditClientDetail, status_code=status.HTTP_201_CREATED)
async def register_payment(
    client_id: int,
    body: CreditPaymentCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> CreditClientDetail:
    client = await _get_client(session, client_id)
    unique_ids = list(dict.fromkeys(body.item_ids))
    rows = (
        await session.execute(
            select(CreditAccountItem, Product)
            .join(Product, Product.id == CreditAccountItem.product_id)
            .where(
                CreditAccountItem.id.in_(unique_ids),
                CreditAccountItem.client_id == client.id,
            ),
        )
    ).all()
    found = {item.id: (item, product) for item, product in rows}
    missing = [i for i in unique_ids if i not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Items not found for this client: {missing}",
        )
    already = [i for i in unique_ids if found[i][0].settled_at is not None]
    if already:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Items already paid: {already}",
        )

    payment = CreditAccountPayment(
        client_id=client.id,
        amount=Decimal("0"),
        note=body.note,
        created_by_user_id=staff.id,
    )
    session.add(payment)
    await session.flush()

    now = datetime.now(timezone.utc)
    amount = Decimal("0")
    for item_id in unique_ids:
        item, product = found[item_id]
        unit_price = product.price
        line_total = (unit_price * item.quantity).quantize(CENTS)
        item.settled_at = now
        item.payment_id = payment.id
        item.settled_unit_price = unit_price
        item.settled_line_total = line_total
        amount += line_total
    payment.amount = amount.quantize(CENTS)

    await audit_record(
        session,
        actor_user_id=staff.id,
        action="credit_account.payment",
        entity_type="credit_account_payment",
        entity_id=str(payment.id),
        payload={
            "client_id": client.id,
            "amount": str(payment.amount),
            "item_ids": unique_ids,
        },
    )
    await session.commit()

    remaining = await compute_client_debt(session, client.id)
    settings = get_settings()
    layout = await load_resolved_receipt_layout(session, settings)
    paid_lines = [
        (
            found[i][1].name,
            found[i][0].quantity,
            found[i][0].settled_unit_price or Decimal("0"),
            found[i][0].settled_line_total or Decimal("0"),
        )
        for i in unique_ids
    ]
    try_print_credit_payment(
        settings,
        layout,
        client_id=client.id,
        client_name=client.name,
        created_at=now,
        lines=paid_lines,
        paid_total=payment.amount,
        remaining_debt=remaining,
    )

    await session.refresh(client)
    return await _build_detail(session, client)
