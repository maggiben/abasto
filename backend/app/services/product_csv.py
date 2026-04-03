from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.models.product import Product

CSV_COLUMNS = [
    "id",
    "name",
    "description",
    "price",
    "cost",
    "margin_percent",
    "barcode",
    "weight_grams",
    "expiration_date",
    "image_url",
    "is_fractional",
    "is_active",
    "quantity",
    "low_stock_threshold",
]

# Semicolon catalog: ean;producto;brand;cat1;cat2;cat3 (legacy / scan.py feeds).
# Required headers (case-insensitive): ean, producto. Optional: brand, cat1–cat3.


def _strip_cell(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _norm_header(h: str) -> str:
    return h.strip().removeprefix("\ufeff").strip()


def _parse_bool(raw: str, row_index: int, field: str) -> bool | str:
    s = raw.strip().lower()
    if s in ("",):
        return "empty"
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    return f"Row {row_index}: invalid {field} (use true/false or 1/0)"


def _parse_decimal(
    raw: str,
    row_index: int,
    field: str,
    *,
    required: bool = False,
    ge: Decimal | None = None,
) -> Decimal | None | str:
    s = raw.strip()
    if s == "":
        if required:
            return f"Row {row_index}: missing {field}"
        return None
    try:
        d = Decimal(s)
    except (InvalidOperation, ValueError):
        return f"Row {row_index}: invalid {field}"
    if ge is not None and d < ge:
        return f"Row {row_index}: {field} must be >= {ge}"
    return d


def _parse_date(raw: str, row_index: int, field: str) -> date | None | str:
    s = raw.strip()
    if s == "":
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return f"Row {row_index}: invalid {field} (use YYYY-MM-DD)"


def _parse_int_id(raw: str) -> int | None | str:
    s = raw.strip()
    if s == "":
        return None
    try:
        v = int(s)
        if v < 1:
            return "invalid id"
        return v
    except ValueError:
        return "invalid id"


def _infer_csv_delimiter(sample: str) -> str:
    first = ""
    for line in sample.splitlines():
        if line.strip():
            first = line
            break
    if not first:
        return ","
    if first.count(";") > first.count(","):
        return ";"
    return ","


def _catalog_extra_description(brand: str, categories: list[str]) -> str | None:
    lines: list[str] = []
    b = brand.strip()
    if b:
        lines.append(f"Brand: {b}")
    trail = " › ".join(c.strip() for c in categories if c and c.strip())
    if trail:
        lines.append(f"Category: {trail}")
    if not lines:
        return None
    return "\n".join(lines)


def _append_duplicate_row_errors(rows: list[ParsedProductRow], errors: list[str]) -> None:
    seen_ids: dict[int, int] = {}
    for r in rows:
        if r.id is not None:
            if r.id in seen_ids:
                errors.append(
                    f"Duplicate id in CSV: {r.id} (rows {seen_ids[r.id]} and {r.row_index})",
                )
            else:
                seen_ids[r.id] = r.row_index

    seen_bc: dict[str, int] = {}
    for r in rows:
        if r.barcode:
            if r.barcode in seen_bc:
                errors.append(
                    f"Duplicate barcode in CSV: {r.barcode} (rows {seen_bc[r.barcode]} and {r.row_index})",
                )
            else:
                seen_bc[r.barcode] = r.row_index


def _parse_catalog_rows(
    reader: csv.DictReader,
    key_by_lower: dict[str, str],
) -> tuple[list[ParsedProductRow], list[str]]:
    """Map ean/producto/catalog metadata into ParsedProductRow; price/qty default to 0."""
    errors: list[str] = []
    rows: list[ParsedProductRow] = []

    def cell(raw: dict[str, str | None], k: str) -> str:
        src = key_by_lower.get(k)
        if src is None:
            return ""
        return _strip_cell(raw.get(src, ""))

    for i, raw in enumerate(reader, start=2):
        if not raw or all(_strip_cell(v) == "" for v in raw.values()):
            continue
        ean = cell(raw, "ean")
        if not ean:
            errors.append(f"Row {i}: ean is required")
            continue
        name = cell(raw, "producto")
        if not name:
            errors.append(f"Row {i}: producto is required")
            continue
        desc = _catalog_extra_description(
            cell(raw, "brand"),
            [cell(raw, "cat1"), cell(raw, "cat2"), cell(raw, "cat3")],
        )
        rows.append(
            ParsedProductRow(
                row_index=i,
                id=None,
                name=name,
                description=desc,
                price=Decimal("0"),
                cost=None,
                margin_percent=None,
                barcode=ean,
                weight_grams=None,
                expiration_date=None,
                image_url=None,
                is_fractional=False,
                is_active=True,
                quantity=Decimal("0"),
                low_stock_threshold=None,
            ),
        )
    return rows, errors


@dataclass
class ParsedProductRow:
    row_index: int
    id: int | None
    name: str
    description: str | None
    price: Decimal
    cost: Decimal | None
    margin_percent: Decimal | None
    barcode: str | None
    weight_grams: Decimal | None
    expiration_date: date | None
    image_url: str | None
    is_fractional: bool
    is_active: bool
    quantity: Decimal
    low_stock_threshold: Decimal | None


def parse_import_csv(content: str) -> tuple[list[ParsedProductRow], list[str]]:
    """Parse CSV text into rows or return global error messages.

    Supports:
    - Full export template: comma or semicolon; columns in CSV_COLUMNS.
    - Legacy catalog: ean;producto;brand;cat1;cat2;cat3 — price and quantity default to 0.
    """
    errors: list[str] = []
    delimiter = _infer_csv_delimiter(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if not reader.fieldnames:
        return [], ["CSV has no header row"]
    fieldnames = reader.fieldnames
    keys_lower = {_norm_header(h).lower() for h in fieldnames}
    if {"ean", "producto"}.issubset(keys_lower):
        key_by_lower = {_norm_header(h).lower(): h for h in fieldnames}
        rows, parse_errors = _parse_catalog_rows(reader, key_by_lower)
        errors.extend(parse_errors)
        _append_duplicate_row_errors(rows, errors)
        return rows, errors

    headers = [_norm_header(h) for h in fieldnames]
    missing = [c for c in CSV_COLUMNS if c not in headers]
    if missing:
        return [], [f"Missing columns: {', '.join(missing)}"]
    # Map canonical column -> actual key from file (normalized)
    key_by_col = {_norm_header(h): h for h in fieldnames}

    rows: list[ParsedProductRow] = []
    for i, raw in enumerate(reader, start=2):
        if not raw or all(_strip_cell(v) == "" for v in raw.values()):
            continue

        def cell(key: str) -> str:
            src = key_by_col.get(key)
            if src is None:
                return ""
            return _strip_cell(raw.get(src, ""))

        eid = _parse_int_id(cell("id"))
        if isinstance(eid, str):
            errors.append(f"Row {i}: {eid}")
            continue

        name = cell("name")
        if not name:
            errors.append(f"Row {i}: name is required")
            continue

        price = _parse_decimal(cell("price"), i, "price", required=True, ge=Decimal("0"))
        if isinstance(price, str):
            errors.append(price)
            continue

        cost = _parse_decimal(cell("cost"), i, "cost", ge=Decimal("0"))
        if isinstance(cost, str):
            errors.append(cost)
            continue

        margin = _parse_decimal(cell("margin_percent"), i, "margin_percent", ge=Decimal("0"))
        if isinstance(margin, str):
            errors.append(margin)
            continue
        if margin is not None and margin > 100:
            errors.append(f"Row {i}: margin_percent must be <= 100")
            continue

        qty = _parse_decimal(cell("quantity"), i, "quantity", required=True, ge=Decimal("0"))
        if isinstance(qty, str):
            errors.append(qty)
            continue

        low = _parse_decimal(cell("low_stock_threshold"), i, "low_stock_threshold", ge=Decimal("0"))
        if isinstance(low, str):
            errors.append(low)
            continue

        w = _parse_decimal(cell("weight_grams"), i, "weight_grams", ge=Decimal("0"))
        if isinstance(w, str):
            errors.append(w)
            continue

        exp = _parse_date(cell("expiration_date"), i, "expiration_date")
        if isinstance(exp, str):
            errors.append(exp)
            continue

        frac = _parse_bool(cell("is_fractional"), i, "is_fractional")
        if isinstance(frac, str):
            errors.append(frac)
            continue
        if frac == "empty":
            frac = False

        active = _parse_bool(cell("is_active"), i, "is_active")
        if isinstance(active, str):
            errors.append(active)
            continue
        if active == "empty":
            active = True

        desc = cell("description") or None
        bc = cell("barcode") or None
        img = cell("image_url") or None

        rows.append(
            ParsedProductRow(
                row_index=i,
                id=eid,
                name=name,
                description=desc,
                price=price,
                cost=cost,
                margin_percent=margin,
                barcode=bc,
                weight_grams=w,
                expiration_date=exp,
                image_url=img,
                is_fractional=frac,
                is_active=active,
                quantity=qty,
                low_stock_threshold=low,
            )
        )

    _append_duplicate_row_errors(rows, errors)
    return rows, errors


def row_to_csv_values(p: Product) -> list[str]:
    inv = p.inventory
    qty = inv.quantity if inv else Decimal("0")
    low = inv.low_stock_threshold if inv else None
    return [
        str(p.id),
        p.name,
        p.description or "",
        str(p.price),
        "" if p.cost is None else str(p.cost),
        "" if p.margin_percent is None else str(p.margin_percent),
        "" if p.barcode is None else p.barcode,
        "" if p.weight_grams is None else str(p.weight_grams),
        "" if p.expiration_date is None else p.expiration_date.isoformat(),
        "" if p.image_url is None else p.image_url,
        "true" if p.is_fractional else "false",
        "true" if p.is_active else "false",
        str(qty),
        "" if low is None else str(low),
    ]


def products_to_csv_bytes(products: list[Product]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS)
    for p in products:
        w.writerow(row_to_csv_values(p))
    return buf.getvalue().encode("utf-8")


def format_export_filename() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"products-{ts}.csv"
