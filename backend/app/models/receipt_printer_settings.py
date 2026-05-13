"""Singleton row (id=1) with JSON payload for receipt / thermal printer layout."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReceiptPrinterSettings(Base):
    __tablename__ = "receipt_printer_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
