from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import get_settings
from app.db.session import get_session
from app.models.order import Sale, SaleLine
from app.models.user import User
from app.schemas.sale import CheckoutRequest, CheckoutResponse
from app.services.audit_service import record as audit_record
from app.services.checkout_common import apply_inventory_deduction, prepare_checkout
from app.services.receipt_printer import try_print_receipt
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
