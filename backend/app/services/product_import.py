from collections.abc import Iterable
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import InventoryItem, Product
from app.services.product_csv import ParsedProductRow

T = TypeVar("T")


def _chunks(values: Iterable[T], size: int = 1000) -> Iterable[list[T]]:
    batch: list[T] = []
    for value in values:
        batch.append(value)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


async def _existing_ids(session: AsyncSession, ids: set[int]) -> set[int]:
    found: set[int] = set()
    for batch in _chunks(ids):
        result = await session.execute(select(Product.id).where(Product.id.in_(batch)))
        found.update(result.scalars().all())
    return found


async def _existing_by_barcode(session: AsyncSession, barcodes: set[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for batch in _chunks(barcodes):
        result = await session.execute(
            select(Product.barcode, Product.id).where(Product.barcode.in_(batch)),
        )
        for barcode, product_id in result.all():
            if barcode is not None:
                found[barcode] = product_id
    return found


async def validate_import_rows(session: AsyncSession, rows: list[ParsedProductRow]) -> list[str]:
    """Database-level validation and EAN/barcode resolution.

    Product ids are internal database ids. Catalog imports normally do not know them, so a
    row with an existing barcode is converted into an update before counts are calculated.
    """
    errors: list[str] = []
    ids = {r.id for r in rows if r.id is not None}
    existing_ids = await _existing_ids(session, ids)
    existing_by_barcode = await _existing_by_barcode(
        session,
        {r.barcode for r in rows if r.barcode},
    )

    for r in rows:
        if r.id is not None:
            if r.id not in existing_ids:
                errors.append(f"Row {r.row_index}: product id {r.id} not found")
                continue
            if r.barcode:
                barcode_owner_id = existing_by_barcode.get(r.barcode)
                if barcode_owner_id is not None and barcode_owner_id != r.id:
                    errors.append(
                        f"Row {r.row_index}: barcode {r.barcode!r} already used by another product",
                    )
        else:
            if r.barcode and (existing_id := existing_by_barcode.get(r.barcode)) is not None:
                r.id = existing_id
    return errors


async def apply_import_rows(
    session: AsyncSession,
    rows: list[ParsedProductRow],
) -> tuple[int, int]:
    """Persist import rows. Caller commits."""
    created = 0
    updated = 0
    for r in rows:
        if r.id is None:
            product = Product(
                name=r.name,
                description=r.description,
                brand=r.brand,
                category=r.category,
                subcategory=r.subcategory,
                category_detail=r.category_detail,
                price=r.price,
                cost=r.cost,
                margin_percent=r.margin_percent,
                tax_rate_percent=r.tax_rate_percent,
                barcode=r.barcode,
                weight_grams=r.weight_grams,
                expiration_date=r.expiration_date,
                image_url=r.image_url,
                is_fractional=r.is_fractional,
                is_active=r.is_active,
            )
            session.add(product)
            await session.flush()
            session.add(
                InventoryItem(
                    product_id=product.id,
                    quantity=r.quantity,
                    low_stock_threshold=r.low_stock_threshold,
                ),
            )
            created += 1
        else:
            stmt = (
                select(Product)
                .options(selectinload(Product.inventory))
                .where(Product.id == r.id)
            )
            result = await session.execute(stmt)
            p = result.scalar_one()
            p.name = r.name
            p.description = r.description
            p.brand = r.brand
            p.category = r.category
            p.subcategory = r.subcategory
            p.category_detail = r.category_detail
            p.price = r.price
            p.cost = r.cost
            p.margin_percent = r.margin_percent
            p.tax_rate_percent = r.tax_rate_percent
            p.barcode = r.barcode
            p.weight_grams = r.weight_grams
            p.expiration_date = r.expiration_date
            p.image_url = r.image_url
            p.is_fractional = r.is_fractional
            p.is_active = r.is_active
            if p.inventory is None:
                session.add(
                    InventoryItem(
                        product_id=p.id,
                        quantity=r.quantity,
                        low_stock_threshold=r.low_stock_threshold,
                    ),
                )
            else:
                p.inventory.quantity = r.quantity
                p.inventory.low_stock_threshold = r.low_stock_threshold
            updated += 1
    return created, updated
