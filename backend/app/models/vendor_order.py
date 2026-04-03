from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import VendorOrderStatus


class VendorOrder(Base):
    __tablename__ = "vendor_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    supplier_name: Mapped[str] = mapped_column(String(500))
    status: Mapped[VendorOrderStatus] = mapped_column(
        SAEnum(VendorOrderStatus, name="vendor_order_status", native_enum=False),
        default=VendorOrderStatus.DRAFT,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["VendorOrderLine"]] = relationship(
        back_populates="vendor_order",
        cascade="all, delete-orphan",
    )


class VendorOrderLine(Base):
    __tablename__ = "vendor_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    vendor_order_id: Mapped[int] = mapped_column(
        ForeignKey("vendor_orders.id", ondelete="CASCADE"),
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal("0"))

    vendor_order: Mapped["VendorOrder"] = relationship(back_populates="lines")
