from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_staff_user
from app.db.session import AsyncSessionLocal
from app.db.session import get_session
from app.models.product import InventoryItem, Product
from app.models.user import User
from app.schemas.csv_import import ProductCsvImportResult, ProductCsvImportStart, ProductCsvImportStatus
from app.schemas.product import ProductCreate, ProductPublic, ProductUpdate, ProductWithInventory
from app.services.audit_service import record as audit_record
from app.services.product_csv import ParsedProductRow, format_export_filename, parse_import_csv, products_to_csv_bytes
from app.services.product_import import apply_import_rows, validate_import_rows
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


@router.get("", response_model=list[ProductWithInventory])
async def list_products(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    q: str | None = Query(
        default=None,
        description="Filter by name or barcode (substring, case-insensitive).",
    ),
    include_inactive: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Product]:
    stmt = (
        select(Product)
        .options(selectinload(Product.inventory))
        .order_by(Product.id.desc())
        .offset(skip)
        .limit(limit)
    )
    if not include_inactive:
        stmt = stmt.where(Product.is_active.is_(True))
    if q:
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(term),
                Product.barcode.ilike(term),
                Product.brand.ilike(term),
                Product.category.ilike(term),
                Product.subcategory.ilike(term),
                Product.category_detail.ilike(term),
            ),
        )
    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


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


@router.post("", response_model=ProductWithInventory, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    staff: Annotated[User, Depends(get_current_staff_user)],
) -> Product:
    if body.barcode:
        existing = await session.execute(
            select(Product.id).where(Product.barcode == body.barcode),
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
        barcode=body.barcode,
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
