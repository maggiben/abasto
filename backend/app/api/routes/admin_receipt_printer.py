import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_staff_user
from app.config import get_settings
from app.db.session import get_session
from app.models.user import User
from app.schemas.receipt_printer_settings import ReceiptPrinterConfigResolved
from app.services.audit_service import record as audit_record
from app.services.receipt_printer import sample_test_checkout, send_receipt_to_printer
from app.services.receipt_printer_config import load_resolved_receipt_layout, upsert_receipt_printer_row

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/settings", response_model=ReceiptPrinterConfigResolved)
async def get_receipt_printer_settings(
    session: Annotated[AsyncSession, Depends(get_session)],
    _staff: Annotated[User, Depends(get_current_staff_user)],
) -> ReceiptPrinterConfigResolved:
    settings = get_settings()
    return await load_resolved_receipt_layout(session, settings)


@router.put("/settings", response_model=ReceiptPrinterConfigResolved)
async def put_receipt_printer_settings(
    body: ReceiptPrinterConfigResolved,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> ReceiptPrinterConfigResolved:
    settings = get_settings()
    await upsert_receipt_printer_row(session, body.model_dump(mode="json"))
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="receipt_printer.settings_update",
        entity_type="receipt_printer_settings",
        entity_id="1",
        payload={"keys": list(body.model_dump(mode="json").keys())},
    )
    await session.commit()
    return await load_resolved_receipt_layout(session, settings)


@router.post("/test-print", status_code=status.HTTP_204_NO_CONTENT)
async def test_receipt_print(
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> Response:
    settings = get_settings()
    if not settings.printer_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Thermal printer is disabled (set PRINTER_ENABLED=true on the API server)",
        )
    layout = await load_resolved_receipt_layout(session, settings)
    sample = sample_test_checkout()
    try:
        await run_in_threadpool(
            send_receipt_to_printer,
            settings,
            sample,
            layout,
            cashier_email=staff.email,
            force=True,
            is_test=True,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Test receipt print failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Test print failed",
        ) from exc

    await audit_record(
        session,
        actor_user_id=staff.id,
        action="receipt_printer.test_print",
        entity_type="receipt_printer_settings",
        entity_id="1",
        payload={},
    )
    await session.commit()
    return Response(status_code=204)
