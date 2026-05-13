from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AnalyticsTotals(BaseModel):
    revenue_pos: Decimal = Field(description="Sum of POS sale totals in range.")
    revenue_web: Decimal = Field(
        description="Sum of customer order totals (non-cancelled) in range.",
    )
    revenue_total: Decimal
    pos_sale_count: int
    web_order_count: int
    inventory_value: Decimal = Field(
        description="Sum of quantity × COALESCE(cost, price) per product.",
    )


class PeriodBucket(BaseModel):
    period_start: datetime
    revenue_pos: Decimal
    revenue_web: Decimal


class AnalyticsSummary(BaseModel):
    range_start: datetime
    range_end: datetime
    granularity: str
    totals: AnalyticsTotals
    buckets: list[PeriodBucket]


class TopProductRow(BaseModel):
    product_id: int
    name: str
    quantity_sold: Decimal = Field(description="Units sold (POS + web, combined).")
    revenue: Decimal = Field(description="Line totals summed (POS + web).")


class TopCategoryRow(BaseModel):
    category: str = Field(description="Product category label; '—' if uncategorized.")
    quantity_sold: Decimal
    revenue: Decimal


class TopSellersOut(BaseModel):
    products: list[TopProductRow]
    categories: list[TopCategoryRow]
