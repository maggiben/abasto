"""Shared stock locking, pricing, and receipt math for POS and web orders."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import InventoryItem, Product
from app.schemas.sale import ReceiptLineOut


@dataclass
class PreparedCheckout:
    products: dict[int, Product]
    inventories: dict[int, InventoryItem | None]
    qty_by_product: dict[int, Decimal]
    receipt_lines: list[ReceiptLineOut]
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    rate: Decimal


class LineLike(Protocol):
    product_id: int
    quantity: Decimal
    unit_price: Decimal | None


async def prepare_checkout(
    session: AsyncSession,
    lines: Sequence[LineLike],
    flat_tax_rate_percent: Decimal | None,
) -> PreparedCheckout:
    qty_by_product: defaultdict[int, Decimal] = defaultdict(Decimal)
    for line in lines:
        qty_by_product[line.product_id] += line.quantity

    product_ids = sorted(qty_by_product.keys())

    products: dict[int, Product] = {}
    for pid in product_ids:
        r = await session.execute(
            select(Product)
            .where(Product.id == pid)
            .with_for_update(),
        )
        p = r.scalar_one_or_none()
        if p is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {pid} not found",
            )
        if not p.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product {pid} is not active",
            )
        products[pid] = p

    inventories: dict[int, InventoryItem | None] = {}
    for pid in product_ids:
        ir = await session.execute(
            select(InventoryItem)
            .where(InventoryItem.product_id == pid)
            .with_for_update(),
        )
        inventories[pid] = ir.scalar_one_or_none()

    for pid, need in qty_by_product.items():
        inv = inventories[pid]
        have = inv.quantity if inv is not None else Decimal("0")
        if have < need:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for product {pid}: need {need}, have {have}"
                ),
            )

    receipt_lines: list[ReceiptLineOut] = []
    subtotal = Decimal("0")

    for line in lines:
        p = products[line.product_id]
        unit = line.unit_price if line.unit_price is not None else p.price
        line_total = (unit * line.quantity).quantize(Decimal("0.0001"))
        subtotal += line_total
        receipt_lines.append(
            ReceiptLineOut(
                product_id=p.id,
                product_name=p.name,
                quantity=line.quantity,
                unit_price=unit,
                line_total=line_total,
            ),
        )

    subtotal = subtotal.quantize(Decimal("0.0001"))
    if flat_tax_rate_percent is not None:
        tax_total = (subtotal * flat_tax_rate_percent / Decimal(100)).quantize(Decimal("0.0001"))
        rate = flat_tax_rate_percent
    else:
        tax_total = Decimal("0")
        for rl in receipt_lines:
            p = products[rl.product_id]
            tax_total += (rl.line_total * p.tax_rate_percent / Decimal(100)).quantize(
                Decimal("0.0001"),
            )
        tax_total = tax_total.quantize(Decimal("0.0001"))
        if subtotal > 0:
            rate = (tax_total / subtotal * Decimal(100)).quantize(Decimal("0.0001"))
        else:
            rate = Decimal("0")
    total = (subtotal + tax_total).quantize(Decimal("0.0001"))

    return PreparedCheckout(
        products=products,
        inventories=inventories,
        qty_by_product=dict(qty_by_product),
        receipt_lines=receipt_lines,
        subtotal=subtotal,
        tax_total=tax_total,
        total=total,
        rate=rate,
    )


def apply_inventory_deduction(prepared: PreparedCheckout) -> None:
    for pid, need in prepared.qty_by_product.items():
        inv = prepared.inventories[pid]
        assert inv is not None
        inv.quantity = (inv.quantity - need).quantize(Decimal("0.0001"))
