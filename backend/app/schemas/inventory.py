from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class LowStockAlert(BaseModel):
    product_id: int
    name: str
    barcode: str | None
    quantity: Decimal
    low_stock_threshold: Decimal


class ExpiringStockAlert(BaseModel):
    product_id: int
    name: str
    barcode: str | None
    expiration_date: date
    quantity: Decimal


class LowStockNotifyResult(BaseModel):
    staff_users: int
    notifications_created: int
    low_stock_products: int


class InventoryUpsert(BaseModel):
    quantity: Decimal = Field(ge=0, description="On-hand quantity (supports fractional units).")
    low_stock_threshold: Decimal | None = Field(
        default=None,
        ge=0,
        description="Alert when quantity is at or below this level.",
    )


class InventoryAdjust(BaseModel):
    delta: Decimal = Field(
        description="Amount to add (positive) or remove (negative) from on-hand quantity.",
    )
