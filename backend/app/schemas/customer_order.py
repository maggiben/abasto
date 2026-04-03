from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import CustomerOrderStatus
from app.schemas.sale import SaleLineIn


class CustomerOrderCreate(BaseModel):
    lines: list[SaleLineIn] = Field(min_length=1)
    guest_email: EmailStr | None = None
    tax_rate_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
    )


class CustomerOrderLineOut(BaseModel):
    product_id: int
    product_name: str
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class CustomerOrderOut(BaseModel):
    id: int
    tracking_token: UUID
    status: CustomerOrderStatus
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    tax_rate_percent: Decimal
    guest_email: str | None
    created_at: datetime
    lines: list[CustomerOrderLineOut]


class AdminCustomerOrderUpdate(BaseModel):
    status: CustomerOrderStatus
