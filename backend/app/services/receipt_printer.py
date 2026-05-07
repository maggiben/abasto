"""Thermal receipt printing over USB (XP-58 / similar). Optional; failures are logged only."""

from __future__ import annotations

import getpass
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


def _wrap_label_lines(name: str, width: int = 32) -> list[str]:
    safe = _ascii_safe(name)
    if not safe:
        return [""]
    lines: list[str] = []
    while safe:
        lines.append(safe[:width])
        safe = safe[width:]
    return lines


def build_product_label_escpos_payload(name: str, barcode_value: str) -> bytes:
    """
    ESC/POS bytes for a centered product name, then CODE128 (same GS k sequence as repo code128.py).
    Barcode data must be ASCII.
    """
    data = barcode_value.encode("ascii")
    if len(data) + 2 > 255:
        raise ValueError("Barcode too long for printer command")

    parts: list[bytes] = [
        b"\x1b\x61\x01",  # center align
    ]
    for line in _wrap_label_lines(name, 32):
        parts.append(line.encode("ascii") + b"\n")

    parts.extend(
        [
            b"\x1b\x61\x01",
            b"\x1d\x68\x64",  # bar code height
            b"\x1d\x77\x02",  # width
            b"\x1d\x48\x02",  # HRI below
            # CODE128 mode 73; {B selects subset B
            b"\x1d\x6b\x49" + bytes([len(data) + 2]) + b"{B" + data,
            b"\n\n\n",
        ],
    )
    return b"".join(parts)


def print_product_label_usb(vendor: int, usb_product: int, name: str, barcode_value: str) -> None:
    """Send a product label to the thermal printer (blocking I/O)."""
    payload = build_product_label_escpos_payload(name, barcode_value)
    _print_raw_usb(vendor, usb_product, payload)


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
    """
    Raw USB write for ESC/POS printers (PyUSB).

    On Linux, if ``usblp`` / CUPS has claimed interface 0, ``detach_kernel_driver(0)``
    is required before userspace I/O (PyUSB docs). We use interface 0 consistently with
    ``_get_usb_out_endpoint`` (``cfg[(0, 0)]``). After printing, ``attach_kernel_driver(0)``
    restores the kernel driver so the device is not left detached until unplug.
    """
    import usb.core  # type: ignore[import-untyped]
    import usb.util  # type: ignore[import-untyped]

    dev = usb.core.find(idVendor=vendor, idProduct=product)
    if dev is None:
        raise RuntimeError(f"USB printer not found (vid={vendor:#06x} pid={product:#06x})")

    # bInterfaceNumber 0 — typical single-interface thermal printer; must match endpoint lookup.
    interface = 0
    kernel_detached = False
    try:
        active = False
        try:
            active = bool(dev.is_kernel_driver_active(interface))
        except NotImplementedError:
            logger.debug("USB is_kernel_driver_active not implemented for this backend")
        except usb.core.USBError as e:
            logger.debug("USB is_kernel_driver_active: %s", e)

        if active:
            try:
                dev.detach_kernel_driver(interface)
                kernel_detached = True
            except usb.core.USBError as e:
                logger.warning(
                    "USB detach_kernel_driver(%s) failed (CUPS/usblp may hold the device): %s",
                    interface,
                    e,
                )

        dev.set_configuration()
        ep = _get_usb_out_endpoint(dev)
        # Init + payload + partial cut (same tail as root print.py)
        data = b"\x1b\x40" + payload + b"\n\x1d\x56\x00"
        written = dev.write(ep.bEndpointAddress, data, timeout=5_000)
        if written != len(data):
            logger.warning("USB write short write: %s vs %s", written, len(data))
    finally:
        try:
            usb.util.dispose_resources(dev)
        except Exception:
            logger.debug("USB dispose_resources failed", exc_info=True)
        if kernel_detached:
            try:
                dev.attach_kernel_driver(interface)
            except usb.core.USBError as e:
                logger.warning(
                    "USB attach_kernel_driver(%s) failed (CUPS/usblp may need replug): %s",
                    interface,
                    e,
                )


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
        logger.info(
            "Receipt print skipped: PRINTER_ENABLED is false (sale_id=%s). "
            "Set PRINTER_ENABLED=true in the API process environment.",
            checkout.sale_id,
        )
        return
    text = build_receipt_text(
        store_name=settings.receipt_store_name,
        checkout=checkout,
        cashier_email=cashier_email,
    )
    payload = text.encode("utf-8", errors="replace")
    vid = settings.printer_usb_vendor
    pid = settings.printer_usb_product
    try:
        logger.info(
            "Receipt print starting: sale_id=%s os_user=%s vid=%#06x pid=%#06x "
            "prefer_escpos=%s profile=%r payload_bytes=%s",
            checkout.sale_id,
            getpass.getuser(),
            vid,
            pid,
            settings.printer_prefer_escpos,
            settings.printer_profile,
            len(payload),
        )
        if settings.printer_prefer_escpos:
            try:
                _print_escpos_usb(vid, pid, settings.printer_profile, text)
                logger.info(
                    "Receipt print finished OK (ESC/POS USB) sale_id=%s",
                    checkout.sale_id,
                )
                return
            except ImportError:
                logger.info("python-escpos not installed; falling back to raw USB print")
            except Exception:
                logger.exception("ESC/POS print failed; trying raw USB")
        _print_raw_usb(vid, pid, payload)
        logger.info("Receipt print finished OK (raw USB) sale_id=%s", checkout.sale_id)
    except Exception:
        logger.exception(
            "Receipt print failed (sale persisted) sale_id=%s vid=%#06x pid=%#06x",
            checkout.sale_id,
            vid,
            pid,
        )
