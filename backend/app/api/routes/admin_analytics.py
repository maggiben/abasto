from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_staff_user
from app.db.session import get_session
from app.models.enums import CustomerOrderStatus
from app.models.order import CustomerOrder, CustomerOrderLine, Sale, SaleLine
from app.models.product import InventoryItem, Product
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsSummary,
    AnalyticsTotals,
    PeriodBucket,
    TopCategoryRow,
    TopProductRow,
    TopSellersOut,
)

router = APIRouter()

Granularity = Literal["day", "week", "month", "year"]


@router.get("/summary", response_model=AnalyticsSummary)
async def analytics_summary(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    range_start: datetime | None = Query(
        default=None,
        description="Inclusive range start (UTC). Defaults to 30 days ago.",
    ),
    range_end: datetime | None = Query(
        default=None,
        description="Exclusive range end (UTC). Defaults to now.",
    ),
    granularity: Granularity = Query(default="day"),
) -> AnalyticsSummary:
    now = datetime.now(timezone.utc)
    end = range_end or now
    start = range_start or (end - timedelta(days=30))
    if end <= start:
        end = start + timedelta(days=1)

    trunc = granularity

    revenue_pos_row = await session.execute(
        select(func.coalesce(func.sum(Sale.total), 0)).where(
            Sale.created_at >= start,
            Sale.created_at < end,
        ),
    )
    revenue_pos = Decimal(str(revenue_pos_row.scalar_one()))

    revenue_web_row = await session.execute(
        select(func.coalesce(func.sum(CustomerOrder.total), 0)).where(
            CustomerOrder.created_at >= start,
            CustomerOrder.created_at < end,
            CustomerOrder.status != CustomerOrderStatus.CANCELLED,
        ),
    )
    revenue_web = Decimal(str(revenue_web_row.scalar_one()))

    pos_count_row = await session.execute(
        select(func.count(Sale.id)).where(
            Sale.created_at >= start,
            Sale.created_at < end,
        ),
    )
    pos_count = int(pos_count_row.scalar_one() or 0)

    web_count_row = await session.execute(
        select(func.count(CustomerOrder.id)).where(
            CustomerOrder.created_at >= start,
            CustomerOrder.created_at < end,
            CustomerOrder.status != CustomerOrderStatus.CANCELLED,
        ),
    )
    web_count = int(web_count_row.scalar_one() or 0)

    inv_row = await session.execute(
        select(
            func.coalesce(
                func.sum(
                    InventoryItem.quantity
                    * func.coalesce(Product.cost, Product.price),
                ),
                0,
            ),
        )
        .select_from(InventoryItem)
        .join(Product, Product.id == InventoryItem.product_id)
        .where(Product.is_active.is_(True)),
    )
    inventory_value = Decimal(str(inv_row.scalar_one()))

    sale_bucket_expr = func.date_trunc(trunc, Sale.created_at)
    sale_b = await session.execute(
        select(sale_bucket_expr, func.coalesce(func.sum(Sale.total), 0))
        .where(Sale.created_at >= start, Sale.created_at < end)
        .group_by(sale_bucket_expr)
        .order_by(sale_bucket_expr),
    )
    web_bucket_expr = func.date_trunc(trunc, CustomerOrder.created_at)
    web_b = await session.execute(
        select(web_bucket_expr, func.coalesce(func.sum(CustomerOrder.total), 0))
        .where(
            CustomerOrder.created_at >= start,
            CustomerOrder.created_at < end,
            CustomerOrder.status != CustomerOrderStatus.CANCELLED,
        )
        .group_by(web_bucket_expr)
        .order_by(web_bucket_expr),
    )

    merged: defaultdict[datetime, dict[str, Decimal]] = defaultdict(
        lambda: {"pos": Decimal("0"), "web": Decimal("0")},
    )
    for row in sale_b.all():
        p, val = row[0], Decimal(str(row[1]))
        if p is not None:
            merged[p]["pos"] += val
    for row in web_b.all():
        p, val = row[0], Decimal(str(row[1]))
        if p is not None:
            merged[p]["web"] += val

    buckets = [
        PeriodBucket(
            period_start=k,
            revenue_pos=v["pos"],
            revenue_web=v["web"],
        )
        for k, v in sorted(merged.items(), key=lambda x: x[0])
    ]

    totals = AnalyticsTotals(
        revenue_pos=revenue_pos,
        revenue_web=revenue_web,
        revenue_total=revenue_pos + revenue_web,
        pos_sale_count=pos_count,
        web_order_count=web_count,
        inventory_value=inventory_value,
    )

    return AnalyticsSummary(
        range_start=start,
        range_end=end,
        granularity=granularity,
        totals=totals,
        buckets=buckets,
    )


def _category_label(raw: str | None) -> str:
    if raw is None:
        return "—"
    s = raw.strip()
    return s if s else "—"


@router.get("/top-sellers", response_model=TopSellersOut)
async def analytics_top_sellers(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_staff_user)],
    range_start: datetime | None = Query(
        default=None,
        description="Inclusive range start (UTC). Defaults to 30 days ago.",
    ),
    range_end: datetime | None = Query(
        default=None,
        description="Exclusive range end (UTC). Defaults to now.",
    ),
    limit: int = Query(default=8, ge=1, le=50),
) -> TopSellersOut:
    now = datetime.now(timezone.utc)
    end = range_end or now
    start = range_start or (end - timedelta(days=30))
    if end <= start:
        end = start + timedelta(days=1)

    pos_products = await session.execute(
        select(
            SaleLine.product_id,
            SaleLine.product_name,
            func.sum(SaleLine.quantity),
            func.sum(SaleLine.line_total),
        )
        .join(Sale, Sale.id == SaleLine.sale_id)
        .where(Sale.created_at >= start, Sale.created_at < end)
        .group_by(SaleLine.product_id, SaleLine.product_name),
    )
    web_products = await session.execute(
        select(
            CustomerOrderLine.product_id,
            Product.name,
            func.sum(CustomerOrderLine.quantity),
            func.sum(CustomerOrderLine.line_total),
        )
        .join(CustomerOrder, CustomerOrder.id == CustomerOrderLine.order_id)
        .join(Product, Product.id == CustomerOrderLine.product_id)
        .where(
            CustomerOrder.created_at >= start,
            CustomerOrder.created_at < end,
            CustomerOrder.status != CustomerOrderStatus.CANCELLED,
        )
        .group_by(CustomerOrderLine.product_id, Product.name),
    )

    merged_p: dict[int, dict[str, object]] = {}
    for row in pos_products.all():
        pid, name, qty, rev = int(row[0]), str(row[1]), Decimal(str(row[2])), Decimal(str(row[3]))
        merged_p[pid] = {
            "name": name,
            "qty": qty,
            "rev": rev,
        }
    for row in web_products.all():
        pid, name, qty, rev = int(row[0]), str(row[1]), Decimal(str(row[2])), Decimal(str(row[3]))
        if pid in merged_p:
            ex = merged_p[pid]
            ex["qty"] = Decimal(str(ex["qty"])) + qty  # type: ignore[assignment]
            ex["rev"] = Decimal(str(ex["rev"])) + rev  # type: ignore[assignment]
            if len(name) > len(str(ex["name"])):
                ex["name"] = name
        else:
            merged_p[pid] = {"name": name, "qty": qty, "rev": rev}

    top_products = sorted(
        (
            TopProductRow(
                product_id=pid,
                name=str(v["name"]),
                quantity_sold=Decimal(str(v["qty"])),
                revenue=Decimal(str(v["rev"])),
            )
            for pid, v in merged_p.items()
        ),
        key=lambda r: r.revenue,
        reverse=True,
    )[:limit]

    pos_cat = await session.execute(
        select(
            Product.category,
            func.sum(SaleLine.quantity),
            func.sum(SaleLine.line_total),
        )
        .select_from(SaleLine)
        .join(Sale, Sale.id == SaleLine.sale_id)
        .join(Product, Product.id == SaleLine.product_id)
        .where(Sale.created_at >= start, Sale.created_at < end)
        .group_by(Product.category),
    )
    web_cat = await session.execute(
        select(
            Product.category,
            func.sum(CustomerOrderLine.quantity),
            func.sum(CustomerOrderLine.line_total),
        )
        .select_from(CustomerOrderLine)
        .join(CustomerOrder, CustomerOrder.id == CustomerOrderLine.order_id)
        .join(Product, Product.id == CustomerOrderLine.product_id)
        .where(
            CustomerOrder.created_at >= start,
            CustomerOrder.created_at < end,
            CustomerOrder.status != CustomerOrderStatus.CANCELLED,
        )
        .group_by(Product.category),
    )

    merged_c: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"qty": Decimal("0"), "rev": Decimal("0")},
    )
    for row in pos_cat.all():
        label = _category_label(row[0])
        merged_c[label]["qty"] += Decimal(str(row[1]))
        merged_c[label]["rev"] += Decimal(str(row[2]))
    for row in web_cat.all():
        label = _category_label(row[0])
        merged_c[label]["qty"] += Decimal(str(row[1]))
        merged_c[label]["rev"] += Decimal(str(row[2]))

    top_categories = sorted(
        (
            TopCategoryRow(
                category=k,
                quantity_sold=v["qty"],
                revenue=v["rev"],
            )
            for k, v in merged_c.items()
        ),
        key=lambda r: r.revenue,
        reverse=True,
    )[:limit]

    return TopSellersOut(products=top_products, categories=top_categories)
