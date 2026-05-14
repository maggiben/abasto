from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    margin_percent: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    tax_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        nullable=False,
        server_default="0",
        default=Decimal("0"),
    )
    barcode: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    weight_grams: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    is_fractional: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    inventory: Mapped["InventoryItem | None"] = relationship(
        back_populates="product",
        uselist=False,
    )


class InventoryItem(Base):
    """Stock for one product (bulk/unit + fractional quantities)."""

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), unique=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0"))
    low_stock_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product: Mapped["Product"] = relationship(back_populates="inventory")
