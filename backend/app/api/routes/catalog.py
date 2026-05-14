from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.models.product import InventoryItem, Product
from app.schemas.product import PriceCheckResponse, ProductCatalogItem

router = APIRouter()


def _quantity(product: Product) -> Decimal:
    if product.inventory is None:
        return Decimal("0")
    return product.inventory.quantity


@router.get("/products", response_model=list[ProductCatalogItem])
async def list_catalog_products(
    session: AsyncSession = Depends(get_session),
    q: str | None = Query(
        default=None,
        description="Search by name (substring) or barcode (substring).",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ProductCatalogItem]:
    stmt = (
        select(Product)
        .options(selectinload(Product.inventory))
        .where(Product.is_active.is_(True))
        .order_by(Product.name.asc())
        .offset(skip)
        .limit(limit)
    )
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Product.name.ilike(term), Product.barcode.ilike(term)),
        )
    result = await session.execute(stmt)
    rows = result.scalars().unique().all()
    return [
        ProductCatalogItem(
            id=p.id,
            name=p.name,
            price=p.price,
            tax_rate_percent=p.tax_rate_percent,
            barcode=p.barcode,
            image_url=p.image_url,
            is_fractional=p.is_fractional,
            quantity=_quantity(p),
        )
        for p in rows
    ]


@router.get("/products/{product_id}", response_model=ProductCatalogItem)
async def get_catalog_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
) -> ProductCatalogItem:
    stmt = (
        select(Product)
        .options(selectinload(Product.inventory))
        .where(Product.id == product_id, Product.is_active.is_(True))
    )
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductCatalogItem(
        id=p.id,
        name=p.name,
        price=p.price,
        tax_rate_percent=p.tax_rate_percent,
        barcode=p.barcode,
        image_url=p.image_url,
        is_fractional=p.is_fractional,
        quantity=_quantity(p),
    )


@router.get("/price-check", response_model=PriceCheckResponse)
async def price_check(
    barcode: str = Query(..., min_length=1, max_length=128),
    session: AsyncSession = Depends(get_session),
) -> PriceCheckResponse:
    stmt = (
        select(Product)
        .options(selectinload(Product.inventory))
        .where(Product.barcode == barcode, Product.is_active.is_(True))
    )
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active product for this barcode",
        )
    return PriceCheckResponse(
        product_id=p.id,
        name=p.name,
        price=p.price,
        tax_rate_percent=p.tax_rate_percent,
        barcode=p.barcode,
        quantity=_quantity(p),
        is_fractional=p.is_fractional,
    )
