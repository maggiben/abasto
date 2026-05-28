"""Thermal receipt printing over USB (XP-58 / similar). Optional; failures are logged only."""

from __future__ import annotations

import base64
import binascii
import getpass
import logging
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.config import Settings
    from app.schemas.receipt_printer_settings import ReceiptPrinterConfigResolved
    from app.schemas.sale import CheckoutResponse

logger = logging.getLogger(__name__)

_RECEIPT_WIDTH = 32

# ESC/POS emphasized (bold) mode — printers treat these as non-printing control codes.
_ESCPOS_BOLD_ON = "\x1b\x45\x01"
_ESCPOS_BOLD_OFF = "\x1b\x45\x00"

_LABELS: dict[str, dict[str, str]] = {
    "es": {
        "sale": "Venta",
        "test_title": "PRUEBA DE IMPRESION",
        "test_sub": "Ticket de prueba",
        "subtotal": "Subtotal",
        "tax": "IVA",
        "tax_with_rate": "IVA ({rate}%)",
        "total": "TOTAL",
        "credit_charge_title": "CUENTA CORRIENTE",
        "credit_unpaid": "** NO PAGADO **",
        "credit_client": "Cliente",
        "credit_this_charge": "Este cargo",
        "credit_total_debt": "DEUDA TOTAL",
        "credit_payment_title": "RECIBO DE PAGO",
        "credit_paid": "PAGADO",
        "credit_remaining": "Saldo pendiente",
        "credit_settled": "CUENTA SALDADA",
    },
    "en": {
        "sale": "Sale",
        "test_title": "PRINT TEST",
        "test_sub": "Test ticket",
        "subtotal": "Subtotal",
        "tax": "Tax",
        "tax_with_rate": "Tax ({rate}%)",
        "total": "TOTAL",
        "credit_charge_title": "STORE CREDIT",
        "credit_unpaid": "** UNPAID **",
        "credit_client": "Client",
        "credit_this_charge": "This charge",
        "credit_total_debt": "TOTAL DEBT",
        "credit_payment_title": "PAYMENT RECEIPT",
        "credit_paid": "PAID",
        "credit_remaining": "Balance due",
        "credit_settled": "ACCOUNT SETTLED",
    },
}


def _money(d: Decimal) -> str:
    return f"{d.quantize(Decimal('0.01')):>10}"


def _ascii_safe(s: str) -> str:
    return s.encode("ascii", "replace").decode("ascii")


def _center_line(s: str, width: int = _RECEIPT_WIDTH) -> str:
    safe = _ascii_safe(s)[:width]
    return safe.center(width)[:width]


def _emit_wrapped_lines(text: str, lines_out: list[str], width: int = _RECEIPT_WIDTH) -> None:
    for raw in (text or "").splitlines():
        chunk = _ascii_safe(raw)
        while chunk:
            lines_out.append(chunk[:width])
            chunk = chunk[width:]


def _label(key: str, locale: str) -> str:
    loc = locale if locale in _LABELS else "es"
    return _LABELS[loc].get(key, _LABELS["es"][key])


def build_receipt_text(
    *,
    checkout: "CheckoutResponse",
    cashier_email: str | None,
    layout: "ReceiptPrinterConfigResolved",
    is_test: bool = False,
) -> str:
    """Receipt body as lines for thermal printers (mostly ASCII; total line may include ESC/POS bold)."""
    ts = checkout.created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    local_dt = ts.astimezone()
    dt = local_dt.strftime("%Y-%m-%d %H:%M")
    loc = layout.receipt_locale

    lines_out: list[str] = []

    _emit_wrapped_lines(layout.header_text, lines_out)
    if layout.header_text.strip():
        lines_out.append("-" * _RECEIPT_WIDTH)

    lines_out.append(_center_line(layout.store_name))
    if layout.greeting_text.strip():
        lines_out.append(_center_line(layout.greeting_text))

    if is_test:
        lines_out.append(_center_line(_label("test_title", loc)))
        lines_out.append(_center_line(_label("test_sub", loc)))
    else:
        lines_out.append(_center_line(f"{_label('sale', loc)} #{checkout.sale_id}"))

    lines_out.append(_center_line(dt))
    lines_out.append("-" * _RECEIPT_WIDTH)

    for ln in checkout.lines:
        name = _ascii_safe(ln.product_name)[:24]
        lines_out.append(name)
        qty = ln.quantity
        unit = ln.unit_price
        tot = ln.line_total
        lines_out.append(f" {qty} x {_money(unit)} {_money(tot)}".rstrip())

    lines_out.append("-" * _RECEIPT_WIDTH)

    if layout.show_subtotal:
        lines_out.append(f"{_label('subtotal', loc):<20}{_money(checkout.subtotal)}")

    if layout.show_tax_lines:
        rate = checkout.tax_rate_percent
        if rate == rate.to_integral():
            rate_s = str(int(rate))
        else:
            rate_s = str(rate)
        tax_key = "tax_with_rate" if rate != 0 else "tax"
        tax_label = _label(tax_key, loc).format(rate=rate_s) if tax_key == "tax_with_rate" else _label("tax", loc)
        lines_out.append(f"{_ascii_safe(tax_label)[:20]:<20}{_money(checkout.tax_total)}")

    total_lbl = _label("total", loc)
    lines_out.append(
        f"{_ESCPOS_BOLD_ON}{total_lbl:<20}{_ESCPOS_BOLD_OFF}{_money(checkout.total)}"
    )
    lines_out.append("-" * _RECEIPT_WIDTH)

    if layout.include_cashier_on_receipt and cashier_email:
        lines_out.append(_ascii_safe(cashier_email)[:_RECEIPT_WIDTH])

    _emit_wrapped_lines(layout.footer_text, lines_out)
    if layout.footer_text.strip():
        lines_out.append("-" * _RECEIPT_WIDTH)

    lines_out.append(_center_line(layout.closing_text))

    return "\n".join(lines_out)


def _fmt_receipt_dt(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def _qty_str(q: Decimal) -> str:
    """Quantity without trailing zeros, never in scientific notation."""
    return format(q.normalize(), "f")


def _receipt_header_lines(layout: "ReceiptPrinterConfigResolved") -> list[str]:
    out: list[str] = []
    _emit_wrapped_lines(layout.header_text, out)
    if layout.header_text.strip():
        out.append("-" * _RECEIPT_WIDTH)
    out.append(_center_line(layout.store_name))
    if layout.greeting_text.strip():
        out.append(_center_line(layout.greeting_text))
    return out


def _receipt_footer_lines(
    layout: "ReceiptPrinterConfigResolved", cashier_email: str | None
) -> list[str]:
    out: list[str] = []
    if layout.include_cashier_on_receipt and cashier_email:
        out.append(_ascii_safe(cashier_email)[:_RECEIPT_WIDTH])
    _emit_wrapped_lines(layout.footer_text, out)
    if layout.footer_text.strip():
        out.append("-" * _RECEIPT_WIDTH)
    out.append(_center_line(layout.closing_text))
    return out


def _credit_item_lines(items: "list[tuple[str, Decimal, Decimal, Decimal]]") -> list[str]:
    out: list[str] = []
    for name, qty, unit, total in items:
        out.append(_ascii_safe(name)[:24])
        out.append(f" {_qty_str(qty)} x {_money(unit)} {_money(total)}".rstrip())
    return out


def build_credit_charge_receipt_text(
    *,
    layout: "ReceiptPrinterConfigResolved",
    client_name: str,
    created_at: datetime,
    lines: "list[tuple[str, Decimal, Decimal, Decimal]]",
    charge_total: Decimal,
    total_debt: Decimal,
) -> str:
    """Debt slip printed when a cart is charged to a client's tab (not paid)."""
    loc = layout.receipt_locale
    out = _receipt_header_lines(layout)
    out.append(_center_line(_label("credit_charge_title", loc)))
    out.append(_center_line(_label("credit_unpaid", loc)))
    out.append("-" * _RECEIPT_WIDTH)
    out.append(f"{_label('credit_client', loc)}: {_ascii_safe(client_name)}"[:_RECEIPT_WIDTH])
    out.append(_fmt_receipt_dt(created_at))
    out.append("-" * _RECEIPT_WIDTH)
    out.extend(_credit_item_lines(lines))
    out.append("-" * _RECEIPT_WIDTH)
    out.append(f"{_label('credit_this_charge', loc):<20}{_money(charge_total)}")
    out.append(
        f"{_ESCPOS_BOLD_ON}{_label('credit_total_debt', loc):<20}{_ESCPOS_BOLD_OFF}{_money(total_debt)}"
    )
    out.append("-" * _RECEIPT_WIDTH)
    out.extend(_receipt_footer_lines(layout, None))
    return "\n".join(out)


def build_credit_payment_receipt_text(
    *,
    layout: "ReceiptPrinterConfigResolved",
    client_name: str,
    created_at: datetime,
    lines: "list[tuple[str, Decimal, Decimal, Decimal]]",
    paid_total: Decimal,
    remaining_debt: Decimal,
) -> str:
    """Receipt printed when a debt is collected. On partial payments it shows the
    remaining balance as a single figure (it does not list the still-owed items)."""
    loc = layout.receipt_locale
    out = _receipt_header_lines(layout)
    out.append(_center_line(_label("credit_payment_title", loc)))
    out.append("-" * _RECEIPT_WIDTH)
    out.append(f"{_label('credit_client', loc)}: {_ascii_safe(client_name)}"[:_RECEIPT_WIDTH])
    out.append(_fmt_receipt_dt(created_at))
    out.append("-" * _RECEIPT_WIDTH)
    out.extend(_credit_item_lines(lines))
    out.append("-" * _RECEIPT_WIDTH)
    out.append(
        f"{_ESCPOS_BOLD_ON}{_label('credit_paid', loc):<20}{_ESCPOS_BOLD_OFF}{_money(paid_total)}"
    )
    if remaining_debt > 0:
        out.append(f"{_label('credit_remaining', loc):<20}{_money(remaining_debt)}")
    else:
        out.append(_center_line(_label("credit_settled", loc)))
    out.append("-" * _RECEIPT_WIDTH)
    out.extend(_receipt_footer_lines(layout, None))
    return "\n".join(out)


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


def _print_raw_usb(vendor: int, product: int, payload: bytes, *, feed_lines_before_cut: int = 0) -> None:
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

    interface = 0
    kernel_detached = False
    feed = b"\n" * max(0, feed_lines_before_cut)
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
        data = b"\x1b\x40" + payload + feed + b"\n\x1d\x56\x00"
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


def _decode_logo_image(logo_b64: str | None) -> Any | None:
    if not logo_b64 or not str(logo_b64).strip():
        return None
    s = str(logo_b64).strip()
    raw = s.split(",", 1)[1] if "," in s and s.lower().startswith("data:") else s
    try:
        decoded = base64.b64decode(raw, validate=True)
    except binascii.Error:
        logger.warning("Invalid logo base64; skipping image")
        return None
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow not installed; skipping receipt logo")
        return None
    try:
        im = Image.open(BytesIO(decoded))
        return im.convert("RGB")
    except Exception:
        logger.exception("Could not decode logo image")
        return None


def _resize_for_thermal(im: Any, max_width: int) -> Any:
    from PIL import Image

    w, h = im.size
    if w <= max_width:
        return im
    ratio = max_width / w
    nh = max(1, int(h * ratio))
    return im.resize((max_width, nh), Image.Resampling.LANCZOS)


def _print_escpos_receipt(
    vendor: int,
    product: int,
    profile: str,
    text: str,
    *,
    logo_image: Any | None,
    logo_max_width: int,
    feed_lines_before_cut: int,
) -> None:
    from escpos.printer import Usb  # type: ignore[import-untyped]

    p = Usb(vendor, product, 0, profile=_resolve_escpos_profile(profile))
    try:
        p.set(align="center", font="a", bold=False, width=1, height=1)
        if logo_image is not None:
            try:
                im = _resize_for_thermal(logo_image, logo_max_width)
                p.image(im, fragment_height=255, center=True, impl="bitImageRaster")
                p.text("\n")
            except Exception:
                logger.exception("ESC/POS logo print failed; continuing with text only")
        p.set(align="left", font="a", bold=False, width=1, height=1)
        for line in text.splitlines():
            p.text(line + "\n")
        for _ in range(max(0, feed_lines_before_cut)):
            p.text("\n")
        p.cut()
    finally:
        try:
            p.close()
        except Exception:  # noqa: S110
            pass


def sample_test_checkout() -> "CheckoutResponse":
    from decimal import Decimal as D

    from app.schemas.sale import CheckoutResponse, ReceiptLineOut

    now = datetime.now(timezone.utc)
    return CheckoutResponse(
        sale_id=0,
        created_at=now,
        subtotal=D("12.50"),
        tax_total=D("1.25"),
        total=D("13.75"),
        tax_rate_percent=D("10"),
        lines=[
            ReceiptLineOut(
                product_id=1,
                product_name="Demo product",
                quantity=D("2"),
                unit_price=D("5.00"),
                line_total=D("10.00"),
            ),
            ReceiptLineOut(
                product_id=2,
                product_name="Otro item",
                quantity=D("1"),
                unit_price=D("2.50"),
                line_total=D("2.50"),
            ),
        ],
    )


def _send_built_text(
    settings: "Settings",
    text: str,
    layout: "ReceiptPrinterConfigResolved",
    *,
    force: bool = False,
    log_id: str = "",
) -> None:
    """Send an already-built receipt body to the USB printer. Raises on I/O errors.

    Logo is printed only when ``printer_prefer_escpos`` is True (python-escpos + Pillow).
    """
    if not force and not settings.printer_enabled:
        return

    payload = text.encode("utf-8", errors="replace")
    vid = settings.printer_usb_vendor
    pid = settings.printer_usb_product
    feed = layout.feed_lines_before_cut
    logo_im = _decode_logo_image(layout.logo_base64) if settings.printer_prefer_escpos else None
    if layout.logo_base64 and not settings.printer_prefer_escpos:
        logger.info("Receipt logo skipped: set PRINTER_PREFER_ESCPOS=true for image printing")

    logger.info(
        "Receipt print starting: id=%s os_user=%s vid=%#06x pid=%#06x "
        "prefer_escpos=%s profile=%r payload_bytes=%s feed_lines=%s",
        log_id,
        getpass.getuser(),
        vid,
        pid,
        settings.printer_prefer_escpos,
        settings.printer_profile,
        len(payload),
        feed,
    )

    if settings.printer_prefer_escpos:
        try:
            _print_escpos_receipt(
                vid,
                pid,
                settings.printer_profile,
                text,
                logo_image=logo_im,
                logo_max_width=layout.logo_max_width,
                feed_lines_before_cut=feed,
            )
            logger.info("Receipt print finished OK (ESC/POS USB) id=%s", log_id)
            return
        except ImportError:
            logger.info("python-escpos not installed; falling back to raw USB print")
        except Exception:
            logger.exception("ESC/POS print failed; trying raw USB")

    _print_raw_usb(vid, pid, payload, feed_lines_before_cut=feed)
    logger.info("Receipt print finished OK (raw USB) id=%s", log_id)


def send_receipt_to_printer(
    settings: "Settings",
    checkout: "CheckoutResponse",
    layout: "ReceiptPrinterConfigResolved",
    *,
    cashier_email: str | None,
    force: bool = False,
    is_test: bool = False,
) -> None:
    """
    Send receipt bytes to USB printer. Raises on device / I/O errors.
    Logo is printed only when ``printer_prefer_escpos`` is True (python-escpos + Pillow).
    """
    if not force and not settings.printer_enabled:
        return

    text = build_receipt_text(
        checkout=checkout,
        cashier_email=cashier_email,
        layout=layout,
        is_test=is_test,
    )
    _send_built_text(settings, text, layout, force=force, log_id=f"sale#{checkout.sale_id}")


def try_print_credit_charge(
    settings: "Settings",
    layout: "ReceiptPrinterConfigResolved | None",
    *,
    client_id: int,
    client_name: str,
    created_at: datetime,
    lines: "list[tuple[str, Decimal, Decimal, Decimal]]",
    charge_total: Decimal,
    total_debt: Decimal,
) -> None:
    """Print a debt slip for a credit-account charge. Never raises — logs errors."""
    if not settings.printer_enabled:
        logger.info("Credit charge slip skipped: PRINTER_ENABLED is false (client=%s)", client_id)
        return
    if layout is None:
        from app.services.receipt_printer_config import default_resolved_layout

        layout = default_resolved_layout(settings)
    try:
        text = build_credit_charge_receipt_text(
            layout=layout,
            client_name=client_name,
            created_at=created_at,
            lines=lines,
            charge_total=charge_total,
            total_debt=total_debt,
        )
        _send_built_text(settings, text, layout, log_id=f"credit-charge:client#{client_id}")
    except Exception:
        logger.exception("Credit charge slip print failed (client=%s)", client_id)


def try_print_credit_payment(
    settings: "Settings",
    layout: "ReceiptPrinterConfigResolved | None",
    *,
    client_id: int,
    client_name: str,
    created_at: datetime,
    lines: "list[tuple[str, Decimal, Decimal, Decimal]]",
    paid_total: Decimal,
    remaining_debt: Decimal,
) -> None:
    """Print a payment receipt for a credit-account collection. Never raises."""
    if not settings.printer_enabled:
        logger.info("Credit payment receipt skipped: PRINTER_ENABLED is false (client=%s)", client_id)
        return
    if layout is None:
        from app.services.receipt_printer_config import default_resolved_layout

        layout = default_resolved_layout(settings)
    try:
        text = build_credit_payment_receipt_text(
            layout=layout,
            client_name=client_name,
            created_at=created_at,
            lines=lines,
            paid_total=paid_total,
            remaining_debt=remaining_debt,
        )
        _send_built_text(settings, text, layout, log_id=f"credit-payment:client#{client_id}")
    except Exception:
        logger.exception("Credit payment receipt print failed (client=%s)", client_id)


def try_print_receipt(
    settings: "Settings",
    checkout: "CheckoutResponse",
    *,
    cashier_email: str | None,
    layout: "ReceiptPrinterConfigResolved | None" = None,
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
    if layout is None:
        from app.services.receipt_printer_config import default_resolved_layout

        layout = default_resolved_layout(settings)
    try:
        send_receipt_to_printer(
            settings,
            checkout,
            layout,
            cashier_email=cashier_email,
            force=force,
            is_test=False,
        )
    except Exception:
        logger.exception(
            "Receipt print failed (sale persisted) sale_id=%s vid=%#06x pid=%#06x",
            checkout.sale_id,
            settings.printer_usb_vendor,
            settings.printer_usb_product,
        )
