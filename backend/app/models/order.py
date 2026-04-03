from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CustomerOrderStatus


class CustomerOrder(Base):
    __tablename__ = "customer_orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    guest_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    tracking_token: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, index=True, default=uuid.uuid4
    )
    status: Mapped[CustomerOrderStatus] = mapped_column(
        SAEnum(CustomerOrderStatus, name="customer_order_status", native_enum=False),
        default=CustomerOrderStatus.PENDING,
    )
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[user_id],
    )
    lines: Mapped[list["CustomerOrderLine"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class CustomerOrderLine(Base):
    __tablename__ = "customer_order_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("customer_orders.id", ondelete="CASCADE"),
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 4))

    order: Mapped["CustomerOrder"] = relationship(back_populates="lines")


class Sale(Base):
    """In-store POS sale (receipt / checkout)."""

    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cashier_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    cashier: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[cashier_user_id],
    )
    lines: Mapped[list["SaleLine"]] = relationship(
        back_populates="sale",
        cascade="all, delete-orphan",
    )


class SaleLine(Base):
    __tablename__ = "sale_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    product_name: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 4))

    sale: Mapped["Sale"] = relationship(back_populates="lines")
