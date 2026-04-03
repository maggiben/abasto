from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.product import InventoryItem, Product
from app.services.product_csv import ParsedProductRow


async def validate_import_rows(session: AsyncSession, rows: list[ParsedProductRow]) -> list[str]:
    """Database-level validation (call after CSV parse succeeds)."""
    errors: list[str] = []
    for r in rows:
        if r.id is not None:
            result = await session.execute(select(Product.id).where(Product.id == r.id))
            if result.scalar_one_or_none() is None:
                errors.append(f"Row {r.row_index}: product id {r.id} not found")
                continue
            if r.barcode:
                clash = await session.execute(
                    select(Product.id).where(
                        Product.barcode == r.barcode,
                        Product.id != r.id,
                    ),
                )
                if clash.scalar_one_or_none() is not None:
                    errors.append(
                        f"Row {r.row_index}: barcode {r.barcode!r} already used by another product",
                    )
        else:
            if r.barcode:
                clash = await session.execute(
                    select(Product.id).where(Product.barcode == r.barcode),
                )
                if clash.scalar_one_or_none() is not None:
                    errors.append(
                        f"Row {r.row_index}: barcode {r.barcode!r} already exists",
                    )
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
                price=r.price,
                cost=r.cost,
                margin_percent=r.margin_percent,
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
            p.price = r.price
            p.cost = r.cost
            p.margin_percent = r.margin_percent
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
