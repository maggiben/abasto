from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SaleLineIn(BaseModel):
    product_id: int = Field(ge=1)
    quantity: Decimal = Field(gt=0, description="Quantity sold (supports fractional weight).")
    unit_price: Decimal | None = Field(
        default=None,
        ge=0,
        description="Override unit price (POS manual price). Defaults to product price.",
    )


class CheckoutRequest(BaseModel):
    lines: list[SaleLineIn] = Field(min_length=1)
    tax_rate_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Sales tax rate; defaults to server default_tax_rate_percent.",
    )


class ReceiptLineOut(BaseModel):
    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class CheckoutResponse(BaseModel):
    sale_id: int
    created_at: datetime
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    tax_rate_percent: Decimal
    lines: list[ReceiptLineOut]


class SaleSummary(BaseModel):
    """Staff listing row for POS sales."""

    id: int
    created_at: datetime
    cashier_user_id: int | None
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal


class SaleLineDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class SaleDetail(BaseModel):
    id: int
    created_at: datetime
    cashier_user_id: int | None
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    lines: list[SaleLineDetail]
