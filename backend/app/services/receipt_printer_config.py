"""Load and merge receipt printer layout from DB + server Settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.receipt_printer_settings import ReceiptPrinterSettings as ReceiptPrinterSettingsRow
from app.schemas.receipt_printer_settings import ReceiptPrinterConfig, ReceiptPrinterConfigResolved

if TYPE_CHECKING:
    from app.config import Settings


def _builtin_thanks(locale: str) -> str:
    return "Gracias" if locale == "es" else "Thank you"


def default_resolved_layout(settings: "Settings") -> ReceiptPrinterConfigResolved:
    return ReceiptPrinterConfigResolved(
        store_name=settings.receipt_store_name,
        header_text="",
        greeting_text="",
        footer_text="",
        closing_text=_builtin_thanks("es"),
        receipt_locale="es",
        show_subtotal=True,
        show_tax_lines=True,
        include_cashier_on_receipt=True,
        feed_lines_before_cut=4,
        logo_base64=None,
        logo_max_width=384,
    )


def merge_receipt_layout(settings: "Settings", stored: ReceiptPrinterConfig | None) -> ReceiptPrinterConfigResolved:
    base = default_resolved_layout(settings)
    if stored is None:
        return base
    store = (stored.store_name or "").strip() or settings.receipt_store_name
    closing = (stored.closing_text or "").strip() or _builtin_thanks(stored.receipt_locale)
    return ReceiptPrinterConfigResolved(
        store_name=store,
        header_text=stored.header_text or "",
        greeting_text=stored.greeting_text or "",
        footer_text=stored.footer_text or "",
        closing_text=closing,
        receipt_locale=stored.receipt_locale,
        show_subtotal=stored.show_subtotal,
        show_tax_lines=stored.show_tax_lines,
        include_cashier_on_receipt=stored.include_cashier_on_receipt,
        feed_lines_before_cut=stored.feed_lines_before_cut,
        logo_base64=stored.logo_base64,
        logo_max_width=stored.logo_max_width,
    )


async def load_resolved_receipt_layout(
    session: AsyncSession,
    settings: "Settings",
) -> ReceiptPrinterConfigResolved:
    result = await session.execute(select(ReceiptPrinterSettingsRow).where(ReceiptPrinterSettingsRow.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        return default_resolved_layout(settings)
    try:
        stored = ReceiptPrinterConfig.model_validate(row.data or {})
    except Exception:
        return default_resolved_layout(settings)
    return merge_receipt_layout(settings, stored)


async def upsert_receipt_printer_row(session: AsyncSession, data: dict) -> None:
    result = await session.execute(select(ReceiptPrinterSettingsRow).where(ReceiptPrinterSettingsRow.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        session.add(ReceiptPrinterSettingsRow(id=1, data=data))
    else:
        row.data = data
