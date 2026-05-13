from __future__ import annotations

import base64
import binascii
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MAX_HEADER_FOOTER = 4000
_MAX_STORE_NAME = 120
_MAX_LOGO_BYTES = 180_000


def _validate_logo_base64(v: str | None) -> str | None:
    if v is None or not str(v).strip():
        return None
    s = str(v).strip()
    raw = s.split(",", 1)[1] if "," in s and s.lower().startswith("data:") else s
    try:
        decoded = base64.b64decode(raw, validate=True)
    except binascii.Error as e:
        raise ValueError("logo_base64 is not valid base64") from e
    if len(decoded) > _MAX_LOGO_BYTES:
        raise ValueError(f"logo image exceeds {_MAX_LOGO_BYTES} bytes decoded")
    return s


class ReceiptPrinterConfig(BaseModel):
    """Payload stored in DB and returned by GET / PUT (effective values after merge on read)."""

    model_config = ConfigDict(str_strip_whitespace=False)

    store_name: str | None = Field(
        default=None,
        max_length=_MAX_STORE_NAME,
        description="Empty: use server env default (receipt_store_name).",
    )
    header_text: str = Field(default="", max_length=_MAX_HEADER_FOOTER)
    greeting_text: str = Field(default="", max_length=500)
    footer_text: str = Field(default="", max_length=_MAX_HEADER_FOOTER)
    closing_text: str | None = Field(
        default=None,
        max_length=500,
        description="None or blank: built-in thank-you line for receipt_locale.",
    )
    receipt_locale: Literal["es", "en"] = "es"
    show_subtotal: bool = True
    show_tax_lines: bool = True
    include_cashier_on_receipt: bool = True
    feed_lines_before_cut: int = Field(default=4, ge=0, le=30)
    logo_base64: str | None = Field(
        default=None,
        description="PNG or JPEG as raw base64 or data URL; used only with ESC/POS path.",
    )
    logo_max_width: int = Field(default=384, ge=80, le=576)

    @field_validator("logo_base64")
    @classmethod
    def validate_logo_size(cls, v: str | None) -> str | None:
        return _validate_logo_base64(v)


class ReceiptPrinterConfigResolved(BaseModel):
    """Merged defaults used when building and printing receipts."""

    model_config = ConfigDict(str_strip_whitespace=False)

    store_name: str
    header_text: str
    greeting_text: str
    footer_text: str
    closing_text: str
    receipt_locale: Literal["es", "en"]
    show_subtotal: bool
    show_tax_lines: bool
    include_cashier_on_receipt: bool
    feed_lines_before_cut: int
    logo_base64: str | None
    logo_max_width: int

    @field_validator("logo_base64")
    @classmethod
    def validate_logo_resolved(cls, v: str | None) -> str | None:
        return _validate_logo_base64(v)
