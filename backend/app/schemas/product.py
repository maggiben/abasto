from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.barcode_allocation import validate_barcode_format


class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    brand: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=255)
    subcategory: str | None = Field(default=None, max_length=255)
    category_detail: str | None = Field(default=None, max_length=255)
    price: Decimal = Field(ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    margin_percent: Decimal | None = Field(default=None, ge=0, le=100)
    barcode: str | None = Field(default=None, max_length=128)
    weight_grams: Decimal | None = Field(default=None, ge=0)
    expiration_date: date | None = None
    image_url: str | None = Field(default=None, max_length=2048)
    is_fractional: bool = False


class ProductCreate(ProductBase):
    @field_validator("barcode", mode="before")
    @classmethod
    def normalize_barcode(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v

    @field_validator("barcode")
    @classmethod
    def barcode_format(cls, v: str | None) -> str | None:
        if v is None:
            return None
        validate_barcode_format(v)
        return v


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    brand: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=255)
    subcategory: str | None = Field(default=None, max_length=255)
    category_detail: str | None = Field(default=None, max_length=255)
    price: Decimal | None = Field(default=None, ge=0)
    cost: Decimal | None = Field(default=None, ge=0)
    margin_percent: Decimal | None = Field(default=None, ge=0, le=100)
    barcode: str | None = Field(default=None, max_length=128)
    weight_grams: Decimal | None = Field(default=None, ge=0)
    expiration_date: date | None = None
    image_url: str | None = Field(default=None, max_length=2048)
    is_fractional: bool | None = None
    is_active: bool | None = None

    @field_validator("barcode", mode="before")
    @classmethod
    def normalize_barcode_update(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v

    @field_validator("barcode")
    @classmethod
    def barcode_format_update(cls, v: str | None) -> str | None:
        if v is None:
            return None
        validate_barcode_format(v)
        return v


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


class PrintLabelBody(BaseModel):
    """Print a product label on the USB thermal printer (server-side)."""

    name: str = Field(min_length=1, max_length=500)
    barcode: str = Field(min_length=1, max_length=128)

    @field_validator("barcode", mode="before")
    @classmethod
    def strip_barcode_print(cls, v: object) -> str:
        if isinstance(v, str):
            return v.strip()
        return str(v)

    @field_validator("barcode")
    @classmethod
    def barcode_format_print(cls, v: str) -> str:
        validate_barcode_format(v)
        return v
