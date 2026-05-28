from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.sale import SaleLineIn


class CreditClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    notes: str | None = None


class CreditClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    notes: str | None = None
    is_active: bool | None = None


class CreditClientSummary(BaseModel):
    """Row for the clients list (with computed live debt)."""

    id: int
    name: str
    phone: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    total_debt: Decimal = Field(description="Sum of unpaid items at current product prices.")
    unpaid_item_count: int


class CreditItemCreate(BaseModel):
    product_id: int = Field(ge=1)
    quantity: Decimal = Field(gt=0, description="Quantity taken (supports fractional weight).")
    note: str | None = Field(default=None, max_length=500)


class CreditItemOut(BaseModel):
    """An unpaid item, priced live from the current product price."""

    id: int
    product_id: int
    product_name: str
    barcode: str | None
    quantity: Decimal
    unit_price: Decimal = Field(description="Current product price.")
    line_total: Decimal = Field(description="quantity x current price.")
    note: str | None
    created_at: datetime


class CreditSettledItemOut(BaseModel):
    """A settled item snapshot, attached to a payment."""

    id: int
    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal = Field(description="Price charged when settled.")
    line_total: Decimal


class CreditPaymentCreate(BaseModel):
    item_ids: list[int] = Field(min_length=1, description="Unpaid item ids to settle.")
    note: str | None = Field(default=None, max_length=500)


class CreditPaymentOut(BaseModel):
    id: int
    amount: Decimal
    note: str | None
    created_by_user_id: int | None
    created_at: datetime
    items: list[CreditSettledItemOut]


class PosCreditClientOut(BaseModel):
    """Lightweight client row for the POS account picker."""

    id: int
    name: str
    phone: str | None
    total_debt: Decimal


class PosChargeAccountRequest(BaseModel):
    client_id: int = Field(ge=1)
    lines: list[SaleLineIn] = Field(min_length=1)


class PosChargeAccountResponse(BaseModel):
    client_id: int
    client_name: str
    charged_total: Decimal = Field(description="Total charged at current prices.")
    item_count: int
    new_total_debt: Decimal


class CreditClientDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    total_debt: Decimal
    items: list[CreditItemOut]
    payments: list[CreditPaymentOut]
