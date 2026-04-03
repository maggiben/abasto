from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import VendorOrderStatus


class VendorOrderLineIn(BaseModel):
    product_id: int = Field(ge=1)
    quantity_ordered: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class VendorOrderCreate(BaseModel):
    supplier_name: str = Field(min_length=1, max_length=500)
    notes: str | None = None
    expected_at: date | None = None
    lines: list[VendorOrderLineIn] = Field(min_length=1)


class VendorOrderLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity_ordered: Decimal
    unit_cost: Decimal
    quantity_received: Decimal


class VendorOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_name: str
    status: VendorOrderStatus
    notes: str | None
    expected_at: date | None
    created_at: datetime
    updated_at: datetime
    lines: list[VendorOrderLineOut]


class VendorOrderUpdate(BaseModel):
    supplier_name: str | None = Field(default=None, min_length=1, max_length=500)
    status: VendorOrderStatus | None = None
    notes: str | None = None
    expected_at: date | None = None


class VendorReceiveRequest(BaseModel):
    line_id: int = Field(ge=1)
    add_quantity: Decimal = Field(gt=0, description="Quantity received now; updates stock.")
