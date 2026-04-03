from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    price: Decimal = Field(ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    margin_percent: Decimal | None = Field(default=None, ge=0, le=100)
    barcode: str | None = Field(default=None, max_length=128)
    weight_grams: Decimal | None = Field(default=None, ge=0)
    expiration_date: date | None = None
    image_url: str | None = Field(default=None, max_length=2048)
    is_fractional: bool = False


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    margin_percent: Decimal | None = Field(default=None, ge=0, le=100)
    barcode: str | None = Field(default=None, max_length=128)
    weight_grams: Decimal | None = Field(default=None, ge=0)
    expiration_date: date | None = None
    image_url: str | None = Field(default=None, max_length=2048)
    is_fractional: bool | None = None
    is_active: bool | None = None


class ProductPublic(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class InventoryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    quantity: Decimal
    low_stock_threshold: Decimal | None
    updated_at: datetime


class ProductCatalogItem(BaseModel):
    """Public catalog row (ecommerce / display)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: Decimal
    barcode: str | None
    image_url: str | None
    is_fractional: bool
    quantity: Decimal = Field(
        description="Available stock (0 if not tracked yet).",
    )


class PriceCheckResponse(BaseModel):
    product_id: int
    name: str
    price: Decimal
    barcode: str | None
    quantity: Decimal
    is_fractional: bool


class ProductWithInventory(ProductPublic):
    inventory: InventoryPublic | None
