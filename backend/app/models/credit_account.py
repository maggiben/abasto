from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CreditAccountClient(Base):
    """A person who buys on a running tab (cuenta corriente)."""

    __tablename__ = "credit_account_clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["CreditAccountItem"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["CreditAccountPayment"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )


class CreditAccountItem(Base):
    """One sold item on a client's tab.

    While unpaid (``settled_at IS NULL``) the price tracks the live product
    price. When settled, the price charged is snapshotted onto the row and the
    item is linked to the settling payment.
    """

    __tablename__ = "credit_account_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("credit_account_clients.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    settled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("credit_account_payments.id", ondelete="SET NULL"), nullable=True
    )
    settled_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    settled_line_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)

    client: Mapped["CreditAccountClient"] = relationship(back_populates="items")
    payment: Mapped["CreditAccountPayment | None"] = relationship(back_populates="items")


class CreditAccountPayment(Base):
    """A payment that settles one or more items on a client's tab."""

    __tablename__ = "credit_account_payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("credit_account_clients.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    client: Mapped["CreditAccountClient"] = relationship(back_populates="payments")
    items: Mapped[list["CreditAccountItem"]] = relationship(back_populates="payment")
