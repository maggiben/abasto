import logging
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import asc, desc, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager, selectinload
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_staff_user
from app.config import get_settings
from app.db.session import AsyncSessionLocal
from app.db.session import get_session
from app.models.order import CustomerOrderLine, SaleLine
from app.models.product import InventoryItem, Product
from app.models.vendor_order import VendorOrderLine
from app.models.user import User
from app.schemas.csv_import import ProductCsvImportResult, ProductCsvImportStart, ProductCsvImportStatus
from app.schemas.product import (
    PrintLabelBody,
    ProductCreate,
    ProductListPage,
    ProductPublic,
    ProductUpdate,
    ProductWithInventory,
)
from app.services.barcode_allocation import allocate_unique_barcode
from app.services.audit_service import record as audit_record
from app.services.product_csv import ParsedProductRow, format_export_filename, parse_import_csv, products_to_csv_bytes
from app.services.product_import import apply_import_rows, validate_import_rows
from app.services.receipt_printer import print_product_label_usb
from app.services.product_import_jobs import (
    add_job_progress,
    complete_job,
    create_job,
    fail_job,
    get_job,
    set_job_running,
)

router = APIRouter()
IMPORT_BATCH_SIZE = 1000
logger = logging.getLogger(__name__)

_SORT_COLUMNS: dict[str, object] = {
    "id": Product.id,
    "name": Product.name,
    "brand": Product.brand,
    "category": func.coalesce(Product.category_detail, Product.subcategory, Product.category),
    "barcode": Product.barcode,
    "price": Product.price,
    "quantity": func.coalesce(InventoryItem.quantity, Decimal("0")),
    "low_stock_threshold": InventoryItem.low_stock_threshold,
    "is_active": Product.is_active,
    "created_at": Product.created_at,
    "updated_at": Product.updated_at,
}


def _product_list_where(
    *,
    q: str | None,
    include_inactive: bool,
    is_active: bool | None,
    name_contains: str | None,
    name_exact: str | None,
    brand_contains: str | None,
    brand_exact: str | None,
    category_contains: str | None,
    category_exact: str | None,
    barcode_contains: str | None,
    barcode_exact: str | None,
    price_min: Decimal | None,
    price_max: Decimal | None,
    price_gt: Decimal | None,
    price_lt: Decimal | None,
    price_eq: Decimal | None,
    quantity_min: Decimal | None,
    quantity_max: Decimal | None,
    quantity_gt: Decimal | None,
    quantity_lt: Decimal | None,
    quantity_eq: Decimal | None,
    low_threshold_min: Decimal | None,
    low_threshold_max: Decimal | None,
    low_threshold_gt: Decimal | None,
    low_threshold_lt: Decimal | None,
    stock_health: Literal["low", "excess"] | None,
) -> list[object]:
    qty = func.coalesce(InventoryItem.quantity, Decimal("0"))
    clauses: list[object] = []
    if is_active is not None:
        clauses.append(Product.is_active.is_(is_active))
    elif not include_inactive:
        clauses.append(Product.is_active.is_(True))
    if q and q.strip():
        term = f"%{q.strip()}%"
        clauses.append(
            or_(
                Product.name.ilike(term),
                Product.barcode.ilike(term),
                Product.brand.ilike(term),
                Product.category.ilike(term),
                Product.subcategory.ilike(term),
                Product.category_detail.ilike(term),
            ),
        )
    if name_exact and name_exact.strip():
        clauses.append(func.lower(Product.name) == name_exact.strip().lower())
    elif name_contains and name_contains.strip():
        clauses.append(Product.name.ilike(f"%{name_contains.strip()}%"))
    if brand_exact and brand_exact.strip():
        clauses.append(func.lower(Product.brand) == brand_exact.strip().lower())
    elif brand_contains and brand_contains.strip():
        clauses.append(Product.brand.ilike(f"%{brand_contains.strip()}%"))
    if category_exact and category_exact.strip():
        cat_expr = func.coalesce(Product.category_detail, Product.subcategory, Product.category)
        clauses.append(func.lower(cat_expr) == category_exact.strip().lower())
    elif category_contains and category_contains.strip():
        cat_expr = func.coalesce(Product.category_detail, Product.subcategory, Product.category)
        clauses.append(cat_expr.ilike(f"%{category_contains.strip()}%"))
    if barcode_exact and barcode_exact.strip():
        clauses.append(func.lower(Product.barcode) == barcode_exact.strip().lower())
    elif barcode_contains and barcode_contains.strip():
        clauses.append(Product.barcode.ilike(f"%{barcode_contains.strip()}%"))
    if price_eq is not None:
        clauses.append(Product.price == price_eq)
    else:
        if price_min is not None:
            clauses.append(Product.price >= price_min)
        if price_max is not None:
            clauses.append(Product.price <= price_max)
        if price_gt is not None:
            clauses.append(Product.price > price_gt)
        if price_lt is not None:
            clauses.append(Product.price < price_lt)
    if quantity_eq is not None:
        clauses.append(qty == quantity_eq)
    else:
        if quantity_min is not None:
            clauses.append(qty >= quantity_min)
        if quantity_max is not None:
            clauses.append(qty <= quantity_max)
        if quantity_gt is not None:
            clauses.append(qty > quantity_gt)
        if quantity_lt is not None:
            clauses.append(qty < quantity_lt)
    if low_threshold_min is not None:
        clauses.append(InventoryItem.low_stock_threshold >= low_threshold_min)
    if low_threshold_max is not None:
        clauses.append(InventoryItem.low_stock_threshold <= low_threshold_max)
    if low_threshold_gt is not None:
        clauses.append(InventoryItem.low_stock_threshold > low_threshold_gt)
    if low_threshold_lt is not None:
        clauses.append(InventoryItem.low_stock_threshold < low_threshold_lt)
    if stock_health == "low":
        clauses.append(
            InventoryItem.low_stock_threshold.isnot(None)
            & (qty <= InventoryItem.low_stock_threshold),
        )
    elif stock_health == "excess":
        clauses.append(
            InventoryItem.low_stock_threshold.isnot(None)
            & (qty > InventoryItem.low_stock_threshold),
        )
    return clauses


async def _run_import_job(job_id: str, rows: list[ParsedProductRow], actor_user_id: int) -> None:
    await set_job_running(job_id)
    created_total = 0
    updated_total = 0
    processed_total = 0
    try:
        async with AsyncSessionLocal() as import_session:
            for offset in range(0, len(rows), IMPORT_BATCH_SIZE):
                batch = rows[offset : offset + IMPORT_BATCH_SIZE]
                created_batch, updated_batch = await apply_import_rows(import_session, batch)
                await import_session.commit()
                processed_total += len(batch)
                created_total += created_batch
                updated_total += updated_batch
                await add_job_progress(
                    job_id,
                    processed=len(batch),
                    created=created_batch,
                    updated=updated_batch,
                )

            await audit_record(
                import_session,
                actor_user_id=actor_user_id,
                action="product.import_csv",
                entity_type="product",
                entity_id=None,
                payload={
                    "rows": processed_total,
                    "created": created_total,
                    "updated": updated_total,
                    "batch_size": IMPORT_BATCH_SIZE,
                },
            )
            await import_session.commit()
        await complete_job(job_id)
    except Exception as exc:  # noqa: BLE001
        await fail_job(job_id, str(exc))


@router.get("", response_model=ProductListPage)
async def list_products(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    q: str | None = Query(
        default=None,
        description="Filter by name or barcode (substring, case-insensitive).",
    ),
    include_inactive: bool = Query(default=False),
    is_active: bool | None = Query(
        default=None,
        description="When set, filters active flag (use with include_inactive to see inactive rows).",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    sort: str = Query(default="id", description="Column id for ordering."),
    order: Literal["asc", "desc"] = Query(default="desc"),
    name_contains: str | None = None,
    name_exact: str | None = None,
    brand_contains: str | None = None,
    brand_exact: str | None = None,
    category_contains: str | None = None,
    category_exact: str | None = None,
    barcode_contains: str | None = None,
    barcode_exact: str | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    price_gt: Decimal | None = None,
    price_lt: Decimal | None = None,
    price_eq: Decimal | None = None,
    quantity_min: Decimal | None = None,
    quantity_max: Decimal | None = None,
    quantity_gt: Decimal | None = None,
    quantity_lt: Decimal | None = None,
    quantity_eq: Decimal | None = None,
    low_threshold_min: Decimal | None = None,
    low_threshold_max: Decimal | None = None,
    low_threshold_gt: Decimal | None = None,
    low_threshold_lt: Decimal | None = None,
    stock_health: Literal["low", "excess"] | None = Query(
        default=None,
        description="low: quantity at or below threshold when threshold is set. excess: quantity above threshold.",
    ),
) -> ProductListPage:
    sort_col = _SORT_COLUMNS.get(sort, Product.id)
    clauses = _product_list_where(
        q=q,
        include_inactive=include_inactive,
        is_active=is_active,
        name_contains=name_contains,
        name_exact=name_exact,
        brand_contains=brand_contains,
        brand_exact=brand_exact,
        category_contains=category_contains,
        category_exact=category_exact,
        barcode_contains=barcode_contains,
        barcode_exact=barcode_exact,
        price_min=price_min,
        price_max=price_max,
        price_gt=price_gt,
        price_lt=price_lt,
        price_eq=price_eq,
        quantity_min=quantity_min,
        quantity_max=quantity_max,
        quantity_gt=quantity_gt,
        quantity_lt=quantity_lt,
        quantity_eq=quantity_eq,
        low_threshold_min=low_threshold_min,
        low_threshold_max=low_threshold_max,
        low_threshold_gt=low_threshold_gt,
        low_threshold_lt=low_threshold_lt,
        stock_health=stock_health,
    )
    count_stmt = (
        select(func.count(Product.id))
        .select_from(Product)
        .outerjoin(InventoryItem, InventoryItem.product_id == Product.id)
        .where(*clauses)
    )
    total = int((await session.execute(count_stmt)).scalar_one())
    order_primary = asc(sort_col) if order == "asc" else desc(sort_col)
    order_id = asc(Product.id) if order == "asc" else desc(Product.id)
    stmt = (
        select(Product)
        .outerjoin(InventoryItem, InventoryItem.product_id == Product.id)
        .options(contains_eager(Product.inventory))
        .where(*clauses)
        .order_by(order_primary, order_id)
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    items_out = list(result.scalars().unique().all())
    return ProductListPage(items=items_out, total=total)


@router.get("/export")
async def export_products_csv(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    include_inactive: bool = Query(default=False),
) -> Response:
    stmt = (
        select(Product)
        .options(selectinload(Product.inventory))
        .order_by(Product.id.asc())
    )
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    result = await session.execute(stmt)
    products = list(result.scalars().unique().all())
    body = products_to_csv_bytes(products)
    name = format_export_filename()
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/import", response_model=ProductCsvImportResult | ProductCsvImportStart)
async def import_products_csv(
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
    background_tasks: BackgroundTasks,
    file: UploadFile = File(
        ...,
        description="UTF-8 CSV: full export columns, or legacy catalog ean;producto;brand;cat1;cat2;cat3 (price/qty=0).",
    ),
    dry_run: bool = Query(default=False),
) -> ProductCsvImportResult:
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be valid UTF-8",
        ) from e
    rows, parse_errors = parse_import_csv(text)
    if parse_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": parse_errors},
        )
    db_errors = await validate_import_rows(session, rows)
    if db_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": db_errors},
        )
    would_create = sum(1 for r in rows if r.id is None)
    would_update = sum(1 for r in rows if r.id is not None)
    if dry_run:
        return ProductCsvImportResult(
            dry_run=True,
            row_count=len(rows),
            created=would_create,
            updated=would_update,
        )
    job = await create_job(
        row_count=len(rows),
        created_estimate=would_create,
        updated_estimate=would_update,
    )
    background_tasks.add_task(_run_import_job, job.job_id, rows, staff.id)
    return ProductCsvImportStart(
        job_id=job.job_id,
        row_count=len(rows),
        created_estimate=would_create,
        updated_estimate=would_update,
    )


@router.get("/import/{job_id}", response_model=ProductCsvImportStatus)
async def get_import_csv_status(
    job_id: str,
    _: Annotated[User, Depends(get_current_staff_user)],
) -> ProductCsvImportStatus:
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    return ProductCsvImportStatus(
        job_id=job.job_id,
        status=job.status,
        row_count=job.row_count,
        processed=job.processed,
        created=job.created,
        updated=job.updated,
        errors=job.errors,
    )


@router.post("/print-label", status_code=status.HTTP_204_NO_CONTENT)
async def print_product_label_route(
    body: PrintLabelBody,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> Response:
    settings = get_settings()
    if not settings.printer_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Thermal printer is disabled (set PRINTER_ENABLED=true on the API server)",
        )
    try:
        await run_in_threadpool(
            print_product_label_usb,
            settings.printer_usb_vendor,
            settings.printer_usb_product,
            body.name,
            body.barcode,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Label print failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Label print failed",
        ) from exc

    await audit_record(
        session,
        actor_user_id=staff.id,
        action="product.print_label",
        entity_type="product",
        entity_id=None,
        payload={"barcode": body.barcode},
    )
    await session.commit()
    return Response(status_code=204)


@router.post("", response_model=ProductWithInventory, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> Product:
    barcode = body.barcode
    if barcode is None:
        barcode = await allocate_unique_barcode(session)
    else:
        existing = await session.execute(
            select(Product.id).where(Product.barcode == barcode),
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Barcode already in use",
            )
    product = Product(
        name=body.name,
        description=body.description,
        brand=body.brand,
        category=body.category,
        subcategory=body.subcategory,
        category_detail=body.category_detail,
        price=body.price,
        cost=body.cost,
        margin_percent=body.margin_percent,
        tax_rate_percent=body.tax_rate_percent,
        barcode=barcode,
        weight_grams=body.weight_grams,
        expiration_date=body.expiration_date,
        image_url=body.image_url,
        is_fractional=body.is_fractional,
    )
    session.add(product)
    await session.flush()
    inv = InventoryItem(product_id=product.id)
    session.add(inv)
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="product.create",
        entity_type="product",
        entity_id=str(product.id),
        payload={"name": product.name},
    )
    await session.commit()
    await session.refresh(product, attribute_names=["inventory"])
    stmt = (
        select(Product)
        .options(selectinload(Product.inventory))
        .where(Product.id == product.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


@router.get("/{product_id}", response_model=ProductWithInventory)
async def get_product(
    product_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
) -> Product:
    stmt = (
        select(Product)
        .options(selectinload(Product.inventory))
        .where(Product.id == product_id)
    )
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return p


@router.patch("/{product_id}", response_model=ProductWithInventory)
async def update_product(
    product_id: int,
    body: ProductUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> Product:
    stmt = select(Product).where(Product.id == product_id)
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    data = body.model_dump(exclude_unset=True)
    if "barcode" in data and data["barcode"] is not None:
        clash = await session.execute(
            select(Product.id).where(
                Product.barcode == data["barcode"],
                Product.id != product_id,
            ),
        )
        if clash.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Barcode already in use",
            )
    for k, v in data.items():
        setattr(p, k, v)
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="product.update",
        entity_type="product",
        entity_id=str(product_id),
        payload=body.model_dump(mode="json", exclude_unset=True),
    )
    await session.commit()
    stmt = (
        select(Product)
        .options(selectinload(Product.inventory))
        .where(Product.id == product_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


@router.delete("/{product_id}", response_model=ProductPublic)
async def deactivate_product(
    product_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> Product:
    stmt = select(Product).where(Product.id == product_id)
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    p.is_active = False
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="product.deactivate",
        entity_type="product",
        entity_id=str(product_id),
        payload=None,
    )
    await session.commit()
    await session.refresh(p)
    return p


@router.delete("/{product_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
async def permanently_delete_product(
    product_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> Response:
    stmt = select(Product).where(Product.id == product_id)
    result = await session.execute(stmt)
    p = result.scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if p.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deactivate the product before permanently deleting it",
        )
    for model in (SaleLine, CustomerOrderLine, VendorOrderLine):
        ref = await session.execute(
            select(model.id).where(model.product_id == product_id).limit(1),
        )
        if ref.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This product is referenced by sales or orders and cannot be permanently deleted",
            )
    name_saved = p.name
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="product.delete_permanent",
        entity_type="product",
        entity_id=str(product_id),
        payload={"name": name_saved},
    )
    await session.delete(p)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", response_model=dict[str, int])
async def deactivate_all_products(
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> dict[str, int]:
    result = await session.execute(
        update(Product)
        .where(Product.is_active.is_(True))
        .values(is_active=False),
    )
    deactivated = int(result.rowcount or 0)
    await audit_record(
        session,
        actor_user_id=staff.id,
        action="product.deactivate_all",
        entity_type="product",
        entity_id=None,
        payload={"deactivated": deactivated},
    )
    await session.commit()
    return {"deactivated": deactivated}
