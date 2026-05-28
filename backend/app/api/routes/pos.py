from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.routes.admin_credit_accounts import compute_client_debt
from app.config import get_settings
from app.db.session import get_session
from app.models.credit_account import CreditAccountClient, CreditAccountItem
from app.models.order import Sale, SaleLine
from app.models.product import Product
from app.models.user import User
from app.schemas.credit_account import (
    PosChargeAccountRequest,
    PosChargeAccountResponse,
    PosCreditClientOut,
)
from app.schemas.sale import CheckoutRequest, CheckoutResponse
from app.services.audit_service import record as audit_record
from app.services.checkout_common import apply_inventory_deduction, prepare_checkout
from app.services.receipt_printer import try_print_credit_charge, try_print_receipt
from app.services.receipt_printer_config import load_resolved_receipt_layout

router = APIRouter()


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    body: CheckoutRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> CheckoutResponse:
    flat = body.tax_rate_percent if body.tax_rate_percent is not None else None
    prepared = await prepare_checkout(session, body.lines, flat)

    sale = Sale(
        cashier_user_id=user.id,
        subtotal=prepared.subtotal,
        tax_total=prepared.tax_total,
        total=prepared.total,
    )
    session.add(sale)
    await session.flush()

    for rl in prepared.receipt_lines:
        session.add(
            SaleLine(
                sale_id=sale.id,
                product_id=rl.product_id,
                product_name=rl.product_name,
                quantity=rl.quantity,
                unit_price=rl.unit_price,
                line_total=rl.line_total,
            ),
        )

    apply_inventory_deduction(prepared)
    line_payload = [rl.model_dump(mode="json") for rl in prepared.receipt_lines]
    await audit_record(
        session,
        actor_user_id=user.id,
        action="pos.checkout",
        entity_type="sale",
        entity_id=str(sale.id),
        payload={
            "sale_id": sale.id,
            "subtotal": str(prepared.subtotal),
            "tax_total": str(prepared.tax_total),
            "total": str(prepared.total),
            "tax_rate_percent": str(prepared.rate),
            "cashier_email": user.email,
            "line_count": len(prepared.receipt_lines),
            "lines": line_payload,
        },
    )
    await session.commit()
    await session.refresh(sale)

    settings = get_settings()
    response = CheckoutResponse(
        sale_id=sale.id,
        created_at=sale.created_at,
        subtotal=prepared.subtotal,
        tax_total=prepared.tax_total,
        total=prepared.total,
        tax_rate_percent=prepared.rate,
        lines=prepared.receipt_lines,
    )
    receipt_layout = await load_resolved_receipt_layout(session, settings)
    try_print_receipt(settings, response, cashier_email=user.email, layout=receipt_layout)
    return response


@router.get("/credit-accounts", response_model=list[PosCreditClientOut])
async def list_credit_accounts_for_pos(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_user)],
    q: str | None = Query(default=None, description="Filter by name or phone (substring)."),
) -> list[PosCreditClientOut]:
    """Active credit clients to charge a sale to, with their current debt."""
    debt = func.coalesce(
        func.sum(CreditAccountItem.quantity * Product.price), Decimal("0")
    ).label("debt")
    stmt = (
        select(CreditAccountClient, debt)
        .outerjoin(
            CreditAccountItem,
            (CreditAccountItem.client_id == CreditAccountClient.id)
            & (CreditAccountItem.settled_at.is_(None)),
        )
        .outerjoin(Product, Product.id == CreditAccountItem.product_id)
        .where(CreditAccountClient.is_active.is_(True))
        .group_by(CreditAccountClient.id)
        .order_by(CreditAccountClient.name.asc())
    )
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            CreditAccountClient.name.ilike(term) | CreditAccountClient.phone.ilike(term),
        )
    rows = (await session.execute(stmt)).all()
    return [
        PosCreditClientOut(
            id=client.id,
            name=client.name,
            phone=client.phone,
            total_debt=Decimal(str(amount or 0)).quantize(Decimal("0.0001")),
        )
        for client, amount in rows
    ]


@router.post("/credit-accounts/charge", response_model=PosChargeAccountResponse)
async def charge_to_credit_account(
    body: PosChargeAccountRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
) -> PosChargeAccountResponse:
    """Put the current cart on a client's tab instead of taking cash.

    Deducts inventory (the goods leave the store now) and records each line as
    an unpaid item priced live against the product. No POS ``Sale`` is created:
    the money is recognized later through a credit-account payment.
    """
    cr = await session.execute(
        select(CreditAccountClient).where(CreditAccountClient.id == body.client_id),
    )
    client = cr.scalar_one_or_none()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credit account client not found",
        )
    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credit account client is not active",
        )

    # Validate products/stock and lock rows; unit price is taken live per product.
    prepared = await prepare_checkout(session, body.lines, None)
    apply_inventory_deduction(prepared)

    charged_total = Decimal("0")
    for line in body.lines:
        product = prepared.products[line.product_id]
        charged_total += (product.price * line.quantity).quantize(Decimal("0.0001"))
        session.add(
            CreditAccountItem(
                client_id=client.id,
                product_id=line.product_id,
                quantity=line.quantity,
            ),
        )
    charged_total = charged_total.quantize(Decimal("0.0001"))

    await audit_record(
        session,
        actor_user_id=user.id,
        action="pos.charge_credit_account",
        entity_type="credit_account_client",
        entity_id=str(client.id),
        payload={
            "client_id": client.id,
            "charged_total": str(charged_total),
            "item_count": len(body.lines),
            "cashier_email": user.email,
        },
    )
    await session.commit()

    new_debt = await compute_client_debt(session, client.id)

    settings = get_settings()
    layout = await load_resolved_receipt_layout(session, settings)
    charge_lines = [
        (rl.product_name, rl.quantity, rl.unit_price, rl.line_total)
        for rl in prepared.receipt_lines
    ]
    try_print_credit_charge(
        settings,
        layout,
        client_id=client.id,
        client_name=client.name,
        created_at=datetime.now(timezone.utc),
        lines=charge_lines,
        charge_total=charged_total,
        total_debt=new_debt,
    )

    return PosChargeAccountResponse(
        client_id=client.id,
        client_name=client.name,
        charged_total=charged_total,
        item_count=len(body.lines),
        new_total_debt=new_debt,
    )
