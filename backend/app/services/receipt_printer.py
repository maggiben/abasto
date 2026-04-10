"""Thermal receipt printing over USB (XP-58 / similar). Optional; failures are logged only."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings
    from app.schemas.sale import CheckoutResponse

logger = logging.getLogger(__name__)


def _money(d: Decimal) -> str:
    return f"{d.quantize(Decimal('0.01')):>10}"


def build_receipt_text(
    *,
    store_name: str,
    checkout: "CheckoutResponse",
    cashier_email: str | None,
) -> str:
    """Plain-text receipt body (ASCII-safe lines)."""
    ts = checkout.created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    local_dt = ts.astimezone()
    dt = local_dt.strftime("%Y-%m-%d %H:%M")
    lines_out: list[str] = [
        store_name.center(32)[:32],
        f"Sale #{checkout.sale_id}".center(32),
        dt.center(32),
        "-" * 32,
    ]
    for ln in checkout.lines:
        name = _ascii_safe(ln.product_name)[:24]
        lines_out.append(name)
        qty = ln.quantity
        unit = ln.unit_price
        tot = ln.line_total
        lines_out.append(
            f" {qty} x {_money(unit)} {_money(tot)}".rstrip(),
        )
    lines_out.append("-" * 32)
    lines_out.append(f"{'Subtotal':<20}{_money(checkout.subtotal)}")
    lines_out.append(
        f"{'Tax (' + str(checkout.tax_rate_percent) + '%)':<20}{_money(checkout.tax_total)}",
    )
    lines_out.append(f"{'TOTAL':<20}{_money(checkout.total)}")
    lines_out.append("-" * 32)
    if cashier_email:
        lines_out.append(_ascii_safe(cashier_email)[:32])
    lines_out.append("Thank you".center(32))
    lines_out.append("")
    return "\n".join(lines_out)


def _ascii_safe(s: str) -> str:
    return s.encode("ascii", "replace").decode("ascii")


def _get_usb_out_endpoint(dev: object):
    import usb.util  # type: ignore[import-untyped]

    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
        == usb.util.ENDPOINT_OUT,
    )
    if ep is None:
        raise RuntimeError("No USB OUT endpoint found for printer")
    return ep


def _print_raw_usb(vendor: int, product: int, payload: bytes) -> None:
    import usb.core  # type: ignore[import-untyped]
    import usb.util  # type: ignore[import-untyped]

    dev = usb.core.find(idVendor=vendor, idProduct=product)
    if dev is None:
        raise RuntimeError(f"USB printer not found (vid={vendor:#06x} pid={product:#06x})")
    if dev.is_kernel_driver_active(0):
        try:
            dev.detach_kernel_driver(0)
        except usb.core.USBError:
            pass
    dev.set_configuration()
    ep = _get_usb_out_endpoint(dev)
    # Init + payload + partial cut (same tail as root print.py)
    data = b"\x1b\x40" + payload + b"\n\x1d\x56\x00"
    written = dev.write(ep.bEndpointAddress, data, timeout=5_000)
    if written != len(data):
        logger.warning("USB write short write: %s vs %s", written, len(data))
    usb.util.dispose_resources(dev)


def _resolve_escpos_profile(name: str) -> str:
    """Use a name from escpos capabilities; unknown names (e.g. hardware labels) fall back."""
    from escpos.capabilities import CAPABILITIES  # type: ignore[import-untyped]

    profiles = CAPABILITIES.get("profiles") or {}
    if name in profiles:
        return name
    logger.debug("ESC/POS profile %r not in capabilities; using default", name)
    return "default"


def _print_escpos_usb(
    vendor: int,
    product: int,
    profile: str,
    text: str,
) -> None:
    from escpos.printer import Usb  # type: ignore[import-untyped]

    p = Usb(vendor, product, 0, profile=_resolve_escpos_profile(profile))
    try:
        p.set(align="left", font="a", bold=False, width=1, height=1)
        for line in text.splitlines():
            p.text(line + "\n")
        p.cut()
    finally:
        try:
            p.close()
        except Exception:  # noqa: S110
            pass


def try_print_receipt(
    settings: "Settings",
    checkout: "CheckoutResponse",
    *,
    cashier_email: str | None,
    force: bool = False,
) -> None:
    """
    If PRINTER_ENABLED (or force=True), send receipt over USB. Never raises — logs errors.

    Uses python-escpos when installed and printer_prefer_escpos is True; otherwise
    raw pyusb write (like repo print.py).
    """
    if not force and not settings.printer_enabled:
        return
    text = build_receipt_text(
        store_name=settings.receipt_store_name,
        checkout=checkout,
        cashier_email=cashier_email,
    )
    vid = settings.printer_usb_vendor
    pid = settings.printer_usb_product
    try:
        if settings.printer_prefer_escpos:
            try:
                _print_escpos_usb(vid, pid, settings.printer_profile, text)
                return
            except ImportError:
                logger.info("python-escpos not installed; falling back to raw USB print")
            except Exception:
                logger.exception("ESC/POS print failed; trying raw USB")
        _print_raw_usb(
            vid,
            pid,
            text.encode("utf-8", errors="replace"),
        )
    except Exception:
        logger.exception("Receipt print failed (sale persisted)")
